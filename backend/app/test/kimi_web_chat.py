"""
调用 Kimi 网页端 (www.kimi.com) 的 Connect 协议接口，获取流式回复 + web search 来源。

与 kimi_test.py 的区别：
  - kimi_test.py 走【官方开发者 API】(api.moonshot.cn + API Key + OpenAI SDK + SSE)。
  - 本脚本走【网页端私有协议】(www.kimi.com/apiv2 + JWT + Connect/gRPC-Web 流式)，
    也就是浏览器里 kimi.com 实际使用的那个接口，用于学习/逆向研究。

============================================================
协议要点（实测自 www.kimi.com 抓包，2026-06）
============================================================

1) 端点（gRPC 风格路径，{包名}.{服务}/{方法}）：
     POST https://www.kimi.com/apiv2/kimi.gateway.chat.v1.ChatService/Chat
     Content-Type: application/connect+json
     Connect-Protocol-Version: 1
     Authorization: Bearer <JWT>

2) 请求体：【必须按 Connect 帧封装】，不是裸 JSON！
   帧格式 = [1字节 flags=0][4字节 大端长度][JSON payload]
   发裸 JSON 会被服务端拒绝（返回 invalid_argument）——实测踩过的坑。
   payload 里关键字段（新建会话首条消息时 chat_id / parent_id 不要传）：
     {
       "scenario": "SCENARIO_K2D5",
       "tools": [{"type":"TOOL_TYPE_SEARCH","search":{}}],  # 声明允许搜索工具
       "message": {
         "role": "user",
         "blocks": [{"message_id":"","text":{"content":"你的问题"}}],
         "scenario": "SCENARIO_K2D5"
       },
       "options": {"thinking": false}       # 搜索场景需禁用思考
     }
   追加到已有会话时才加：顶层 "chat_id" 和 message 里的 "parent_id"。

3) 响应：一条 Connect 流。每帧 = [1字节 flags][4字节 大端长度][payload JSON]
     - flags=0x00 普通数据帧；0x02 结束帧(trailer)；0x01 压缩帧(本脚本不处理压缩)
     - 每个 payload 是一个「事件」：{op, mask, eventOffset, ...载荷容器}

4) op + mask 增量更新模型（核心思想）：
     服务端不重发整条消息，而是告诉你「在哪个路径(mask)上做什么(op)」。
       op=set      整体设置；  op=append   追加片段
     常见 mask：
       chat.lastRequest / message / message.status / chat.name
       block.text                 正文块（首次 set）
       block.text.content         正文内容（多次 append，逐 token 流出）
       block.tool / block.tool.args / block.tool.contents   搜索工具块
       message.refs.searchChunks  来源镜像到「可引用来源表」

5) 回复正文 = 把所有 {op:append, mask:block.text.content}.block.text.content 按序拼接。

6) 信息来源 = block.tool.contents（搜索结果数组），同时镜像到 message.refs.searchChunks。
   每条来源结构（关键字段）：
     { searchResult: { id, base: {title, url, siteName, iconUrl, snippet, publishTime},
                       refIndex: "web_search:1#0" } }
   正文里的引用用 Unicode 私有区(PUA)字符内联标记，如：
     \\ue3a0cite\\ue3a3web_search:1#2\\ue3a8
   refIndex 就是「正文角标 ↔ 来源卡片」的桥梁。

参考：实测中并非每次都触发搜索——是否调用 $web_search 由模型运行时(function calling)决定，
即使请求里声明了 TOOL_TYPE_SEARCH，模型也可能直接用自身知识回答（此时无 block.tool 事件）。
"""

from __future__ import annotations

import base64
import json
import re
import struct
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional
from urllib.parse import urlencode  # noqa: F401  (保留给后续可能的查询参数扩展)

# stdlib 的 urllib 即可流式读取，无需第三方依赖；若环境装了 requests 也可换用。
import urllib.request


# ============================================================
# 鉴权 ——【只需填 JWT 一个值】
# ------------------------------------------------------------
# JWT 从浏览器抓包获取：DevTools → Network → 任意一次 ChatService/Chat 请求
# → 复制请求头 Authorization: Bearer <这里这一长串>。
#   - 它也等于 cookie 里 kimi-auth 的值（HttpOnly，页面 JS 读不到，必须手动复制）。
#   - 约 30 天过期（JWT 内 exp 字段），过期后重新登录 kimi.com 再抓一次即可。
#   - 过期表现为服务端返回 {"error":{"code":"unauthenticated"}}。
#
# device_id / session_id / traffic_id 这三个值【不再需要手填】——它们编码在
# JWT 内部（见下方 _JWT_CLAIMS 的解析），脚本会自动提取，保证永远和 JWT 一致，
# 避免"JWT 改了但 device_id 忘改"导致的不一致错误。
#
# 关于 x-msh-shield-data（风控头）：真实网页端请求会带这个头，它是前端 JS
# 实时生成的设备风控签名。实测【不带这个头也能成功】——只要请求体按
# Connect 帧正确封装 + JWT 有效即可。所以本脚本不处理 shield。
# ============================================================
JWT = (
    "eyJhbGciOiJIUzUxMiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJ1c2VyLWNlbnRlciIsImV4cCI6MTc4NDE2NjY4MCwiaWF0IjoxNzgxNTc0NjgwL"
    "CJqdGkiOiJkOG9hbzY0cWRxZWxza20zdjRvZyIsInR5cCI6ImFjY2VzcyIsImFwcF9pZCI6Imt"
    "pbWkiLCJzdWIiOiJjc2Rqb2Zrcm1lZTljaTdmbzIwZyIsInNwYWNlX2lkIjoiY3Nkam9ma3JtZ"
    "WU5Y2k3Zm8xdmciLCJhYnN0cmFjdF91c2VyX2lkIjoiY3Nkam9ma3JtZWU5Y2k3Zm8xdjAiLCJz"
    "c2lkIjoiMTczMTA4NjQ5OTk1ODYzOTgwMiIsImRldmljZV9pZCI6Ijc2NTE4MDQxMTQxMDMzMj"
    "kyOTEiLCJyZWdpb24iOiJjbiIsIm1lbWJlcnNoaXAiOnsibGV2ZWwiOjEwfX0."
    "1QH050GH1_j4VnDT2BJUwmr_U0F-i1jMsQvcrEuKS6ajC_wVIu6fSzEeQgLz3rReCryAz-stX9nnI8KjmDwqqg"
)
X_MSH_DEVICE_ID = "7651804114103329291"
X_MSH_SESSION_ID = "1731086499958639802"
X_TRAFFIC_ID = "csdjofkrmee9ci7fo20g"


def _decode_jwt_claims(token: str) -> Dict[str, Any]:
    """解码 JWT 的中间段（payload），返回 claims dict。

    JWT 结构 = header.payload.signature，三段都是 base64url 编码。
    这里只解码 payload（不验证签名——验证需要服务端密钥，客户端无需做）。
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError(f"非法 JWT 格式：期望 3 段，实际 {len(parts)} 段")
    payload_b64 = parts[1]
    # base64url 编码可能缺末尾的 = 填充，补齐到 4 的倍数
    payload_b64 += "=" * (-len(payload_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(payload_b64))


# 从 JWT 自动派生 device_id / session_id / traffic_id，保证三者永远和 JWT 内部一致。
# 字段对应关系（解码 JWT payload 可见）：
#   device_id  ← claims["device_id"]   （浏览器设备指纹）
#   session_id ← claims["ssid"]        （登录会话 id）
#   traffic_id ← claims["sub"]         （用户 id，用作流量统计标识）
_JWT_CLAIMS = _decode_jwt_claims(JWT)
X_MSH_DEVICE_ID = str(_JWT_CLAIMS["device_id"])
X_MSH_SESSION_ID = str(_JWT_CLAIMS["ssid"])
X_TRAFFIC_ID = str(_JWT_CLAIMS["sub"])

# cookie 也建议带上（服务端会校验 kimi-auth；JWT 已包含同样身份，但带上更稳妥）。
COOKIE = "kimi-auth=" + JWT

CHAT_URL = "https://www.kimi.com/apiv2/kimi.gateway.chat.v1.ChatService/Chat"


# ============================================================
# 数据结构
# ============================================================
@dataclass
class Source:
    """单条 web search 来源（信息卡片）。"""

    ref_index: str = ""          # 如 "web_search:1#0"，正文角标靠它关联
    title: str = ""
    url: str = ""
    site_name: str = ""
    icon_url: str = ""
    snippet: str = ""
    publish_time: str = ""

    @classmethod
    def from_search_result(cls, sr: Dict[str, Any]) -> "Source":
        base = sr.get("base") or sr.get("searchBase") or {}
        return cls(
            ref_index=str(sr.get("refIndex") or sr.get("ref_index") or ""),
            title=str(base.get("title") or ""),
            url=str(base.get("url") or ""),
            site_name=str(base.get("siteName") or base.get("site_name") or ""),
            icon_url=str(base.get("iconUrl") or base.get("icon_url") or ""),
            snippet=str(base.get("snippet") or ""),
            publish_time=str(base.get("publishTime") or base.get("publish_time") or ""),
        )

    def brief(self, idx: int) -> str:
        head = f"[{idx}] {self.title}".strip()
        meta = self.site_name or self._host()
        line = head
        if meta:
            line += f"  ({meta})"
        if self.url:
            line += f"\n    {self.url}"
        if self.snippet:
            snip = self.snippet.replace("\n", " ")
            line += f"\n    {snip[:160]}{'…' if len(snip) > 160 else ''}"
        return line

    def _host(self) -> str:
        m = re.match(r"https?://([^/]+)", self.url)
        return m.group(1) if m else ""


@dataclass
class ChatResult:
    """一次对话的解析结果。"""

    text: str = ""                               # 还原后的正文（已剥离 PUA 引用标记）
    raw_text: str = ""                           # 原始正文（保留 PUA 标记，便于调试）
    sources: List[Source] = field(default_factory=list)
    search_queries: List[str] = field(default_factory=list)  # 模型生成的搜索词
    chat_id: str = ""                            # 本次（可能新建的）会话 id
    chat_name: str = ""                          # 自动生成的会话标题
    triggered_search: bool = False
    error: Optional[str] = None


# ============================================================
# Connect 流解析：flags + 4字节大端长度 + payload
# ============================================================
def iter_connect_frames(byte_iter: Iterator[bytes]) -> Iterator[Dict[str, Any]]:
    """从字节流里逐帧解析，yield 出每个 JSON 事件 dict。

    byte_iter: 每次产出一段 bytes（按网络包到达）。本函数内部维护缓冲区。
    帧格式：[1字节 flags][4字节 大端 length][length 字节 payload]
    """
    buf = bytearray()
    for chunk in byte_iter:
        if not chunk:
            continue
        buf.extend(chunk)
        # 尝试从缓冲区里尽量多地切出完整帧
        while True:
            if len(buf) < 5:
                break
            flags = buf[0]
            length = struct.unpack(">I", bytes(buf[1:5]))[0]
            if len(buf) < 5 + length:
                break  # 数据还没到齐，等下一个 chunk
            payload_bytes = bytes(buf[5 : 5 + length])
            del buf[: 5 + length]
            # flags bit1(0x02)=结束帧，payload 是 trailer（如 "{}"）；bit0(0x01)=压缩
            if flags & 0x01:
                # 压缩帧需要解压，网页端实测未出现，这里跳过避免误解析
                continue
            if not payload_bytes:
                continue
            try:
                obj = json.loads(payload_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            yield obj


def _urllib_byte_iter(resp: Any, chunk_size: int = 4096) -> Iterator[bytes]:
    """把 urllib 的 HTTPResponse 包装成按块迭代的字节流。"""
    while True:
        chunk = resp.read(chunk_size)
        if not chunk:
            break
        yield chunk


# ============================================================
# 发起请求
# ============================================================
def build_headers() -> Dict[str, str]:
    return {
        "content-type": "application/connect+json",
        "connect-protocol-version": "1",
        "authorization": f"Bearer {JWT}",
        "x-traffic-id": X_TRAFFIC_ID,
        "x-msh-platform": "web",
        "x-msh-version": "1.0.0",
        "x-msh-device-id": X_MSH_DEVICE_ID,
        "x-msh-session-id": X_MSH_SESSION_ID,
        "x-language": "zh-CN",
        "r-timezone": "Asia/Shanghai",
        "cookie": COOKIE,
        # 伪装成浏览器，部分网关会校验 UA
        "user-agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
        ),
        "origin": "https://www.kimi.com",
        "referer": "https://www.kimi.com/",
    }


def build_body(
    question: str,
    chat_id: str = "",
    parent_id: str = "",
    enable_search: bool = True,
) -> bytes:
    """构造请求体并按 Connect 协议帧封装后返回 bytes。

    【关键】请求体不是裸 JSON，而是要包成 Connect unary 帧：
        [1字节 flags=0][4字节 大端长度][JSON payload]
    发裸 JSON 会被服务端拒绝（invalid_argument）——这是实测踩过的坑。

    新建会话首条消息时，chat_id / parent_id 必须【完全不传该字段】
    （传空字符串 "" 同样会被拒绝）。只有追加到已有会话时才传有效值。
    """
    payload: Dict[str, Any] = {
        "scenario": "SCENARIO_K2D5",
        "message": {
            "role": "user",
            "blocks": [{"message_id": "", "text": {"content": question}}],
            "scenario": "SCENARIO_K2D5",
        },
        "options": {"thinking": False},  # 搜索场景需禁用思考
    }
    if enable_search:
        payload["tools"] = [{"type": "TOOL_TYPE_SEARCH", "search": {}}]
    # 仅在追加到已有会话时才带上 chat_id / parent_id（空值不传）
    if chat_id:
        payload["chat_id"] = chat_id
    if parent_id:
        payload["message"]["parent_id"] = parent_id

    json_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return _encode_connect_frame(json_bytes)


def _encode_connect_frame(payload: bytes, flags: int = 0) -> bytes:
    """把 JSON payload 封装成单个 Connect 帧：flags(1B) + 长度(4B大端) + payload。"""
    return bytes([flags & 0xFF]) + struct.pack(">I", len(payload)) + payload


# ============================================================
# 正文里的 PUA 引用标记处理
# ============================================================
# 实测正文用 Unicode 私用区(PUA)字符内联标记引用，形如：
#   \ue3a0cite\ue3a3web_search:1#0\ue3a8
# 一个 cite 标记里可能合并多个引用（用 \ue3a3 分隔），如：
#   \ue3a0cite\ue3a3web_search:1#0\ue3a3web_search:1#3\ue3a8
# 即"起始符cite + 若干个(分隔符refIndex) + 结束符"。
# 先非贪婪匹配整块 \ue3a0cite ... \ue3a8，再在块内按 \ue3a3 拆 refIndex。
_CITE_PATTERN = re.compile(r"\ue3a0cite(.*?)\ue3a8")
# 兜底：有些版本用 [[ref]] 风格
_BRACKET_PATTERN = re.compile(r"\[\[(?:cite:)?([A-Za-z0-9_:#\-./]+)\]\]")


def strip_inline_cites(text: str) -> tuple[str, List[str]]:
    """剥离正文里的引用标记，返回 (干净正文, 出现过的 refIndex 顺序列表)。

    一个标记可能合并多个引用，如 \\ue3a0cite\\ue3a3A\\ue3a3B\\ue3a8，
    会把 A、B 都加入 refs 列表。
    """
    refs: List[str] = []

    def _collect_pua(m: re.Match) -> str:
        inner = m.group(1)  # 形如 "\ue3a3web_search:1#0\ue3a3web_search:1#3"
        # 按 \ue3a3 分隔，取出每段 refIndex（跳过空段）
        for seg in inner.split("\ue3a3"):
            seg = seg.strip()
            if seg:
                refs.append(seg)
        return ""  # 直接移除标记；如需在原位留角标，可改成 f"[{idx}]"

    def _collect_bracket(m: re.Match) -> str:
        refs.append(m.group(1))
        return ""

    cleaned = _CITE_PATTERN.sub(_collect_pua, text)
    cleaned = _BRACKET_PATTERN.sub(_collect_bracket, cleaned)
    return cleaned, refs


# ============================================================
# 主流程：发送 + 流式解析
# ============================================================
def chat(
    question: str,
    chat_id: str = "",
    parent_id: str = "",
    enable_search: bool = True,
    on_text: Optional[object] = None,
    timeout: float = 60.0,
) -> ChatResult:
    """发一次消息，流式收集结果。

    on_text: 可选回调 `on_text(delta: str)`，每收到一段正文增量就调用一次，
             便于做"打字机"实时输出。
    """
    result = ChatResult()
    body = build_body(question, chat_id, parent_id, enable_search)
    req = urllib.request.Request(
        CHAT_URL, data=body, headers=build_headers(), method="POST"
    )

    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        result.error = f"HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}"
        return result
    except Exception as e:  # noqa: BLE001
        result.error = f"请求失败: {e}"
        return result

    text_parts: List[str] = []
    raw_parts: List[str] = []
    sources_by_ref: Dict[str, Source] = {}
    args_buf: List[str] = []  # 累积 block.tool.args 的流式片段

    with resp:
        for ev in iter_connect_frames(_urllib_byte_iter(resp)):
            # 错误帧
            if isinstance(ev, dict) and ev.get("error"):
                result.error = json.dumps(ev["error"], ensure_ascii=False)
                break

            mask = ev.get("mask")
            op = ev.get("op")

            # 会话 id / 标题
            chat_obj = ev.get("chat")
            if isinstance(chat_obj, dict):
                if chat_obj.get("id"):
                    result.chat_id = chat_obj["id"]
                if chat_obj.get("name"):
                    result.chat_name = chat_obj["name"]

            # 正文：set 首块 + append 后续块
            if mask == "block.text":
                block = ev.get("block") or {}
                c = ((block.get("text") or {}).get("content")) or ""
                if c:
                    raw_parts.append(c)
                    if on_text:
                        on_text(c)
            elif mask == "block.text.content" and op == "append":
                block = ev.get("block") or {}
                c = ((block.get("text") or {}).get("content")) or ""
                if c:
                    raw_parts.append(c)
                    if on_text:
                        on_text(c)

            # 搜索工具块出现 = 触发了搜索
            elif mask == "block.tool":
                result.triggered_search = True

            # 搜索词（模型逐 token 生成，需把多次 append 的片段拼成完整 JSON 再解析）
            elif mask == "block.tool.args" and op == "append":
                block = ev.get("block") or {}
                args_str = ((block.get("tool") or {}).get("args")) or ""
                if args_str:
                    args_buf.append(args_str)

            # 搜索结果列表（来源本体）
            elif mask == "block.tool.contents":
                result.triggered_search = True
                block = ev.get("block") or {}
                contents = (block.get("tool") or {}).get("contents") or []
                for item in contents:
                    sr = item.get("searchResult") or item
                    src = Source.from_search_result(sr)
                    if src.ref_index:
                        sources_by_ref[src.ref_index] = src
                    else:
                        sources_by_ref[f"_{len(sources_by_ref)}"] = src

            # 来源镜像（与 contents 等价，作为兜底来源）
            elif mask == "message.refs.searchChunks":
                result.triggered_search = True
                msg = ev.get("message") or {}
                refs = msg.get("refs") or {}
                for chunk in refs.get("searchChunks") or []:
                    sr = chunk.get("searchResult") or chunk
                    src = Source.from_search_result(sr)
                    if src.ref_index:
                        sources_by_ref[src.ref_index] = src

    # 把累积的搜索词片段拼成完整 JSON 再解析
    if args_buf:
        _parse_search_args("".join(args_buf), result)

    # 还原正文，剥离引用标记
    result.raw_text = "".join(raw_parts)
    result.text, cited_refs = strip_inline_cites(result.raw_text)

    # 来源排序：按正文引用顺序优先，未引用的按 ref_index 排在后面
    cited_set = []
    seen = set()
    for r in cited_refs:
        if r in sources_by_ref and r not in seen:
            cited_set.append(r)
            seen.add(r)
    for k in sorted(sources_by_ref):
        if k not in seen:
            cited_set.append(k)
            seen.add(k)
    result.sources = [sources_by_ref[k] for k in cited_set]
    return result


def _parse_search_args(raw: str, result: ChatResult) -> None:
    """解析累积完整的 block.tool.args JSON，提取搜索词列表。"""
    if not raw:
        return
    try:
        obj = json.loads(raw)
        queries = obj.get("queries") or obj.get("search_query") or obj.get("query")
        if isinstance(queries, list):
            result.search_queries = [str(q) for q in queries]
        elif isinstance(queries, str):
            result.search_queries = [queries]
    except json.JSONDecodeError:
        # 兜底：搜索词偶尔以非 JSON 纯文本形式出现
        result.search_queries = [raw]


# ============================================================
# CLI
# ============================================================
def _print_stream(delta: str) -> None:
    sys.stdout.write(delta)
    sys.stdout.flush()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    import argparse

    p = argparse.ArgumentParser(
        description="调用 Kimi 网页端 Connect 协议接口，获取流式回复 + web search 来源"
    )
    p.add_argument("question", nargs="?", default="2026年最新的AI大模型新闻", help="要提问的内容")
    p.add_argument("--chat-id", default="", help="已有会话 id（留空=新建会话）")
    p.add_argument("--parent-id", default="", help="上条消息 id（留空=首条）")
    p.add_argument("--no-search", action="store_true", help="不声明搜索工具")
    p.add_argument(
        "--stream",
        action="store_true",
        help="实时打印流式正文（打字机效果；注意：引用标记会暂时以原始形式可见，结束后才清洗）",
    )
    args = p.parse_args()

    if not JWT or JWT.startswith("请填"):
        print("【请先填写脚本顶部的 JWT / device_id 等变量】", file=sys.stderr)
        sys.exit(1)

    # 默认不实时打印（引用标记分散在流里，实时清洗不可靠）；--stream 时才打字机输出。
    on_text = _print_stream if args.stream else None
    if args.stream:
        print("========== 流式回复（实时）==========")
    result = chat(
        args.question,
        chat_id=args.chat_id,
        parent_id=args.parent_id,
        enable_search=not args.no_search,
        on_text=on_text,
    )
    if args.stream:
        print()  # 流式输出后补一个换行
    # 无论是否流式，都打印一份清洗后的完整正文
    print("========== 回复正文 ==========")
    print(result.text)

    if result.error:
        print(f"\n[错误] {result.error}", file=sys.stderr)
        sys.exit(2)

    print("\n========== 搜索词 ==========")
    if result.search_queries:
        for i, q in enumerate(result.search_queries, 1):
            print(f"[{i}] {q}")
    elif result.triggered_search:
        print("(触发了搜索，但未捕获到搜索词)")
    else:
        print("(本次未触发联网搜索 —— 是否调用 $web_search 由模型运行时决定)")

    print("\n========== 信息来源 ==========")
    if result.sources:
        for i, s in enumerate(result.sources, 1):
            print(s.brief(i))
            print()
    else:
        print("(无来源)")

    print("========== 元信息 ==========")
    print(f"会话 id : {result.chat_id}")
    print(f"会话标题: {result.chat_name}")
    print(f"触发搜索: {result.triggered_search}")
    print(f"来源数量: {len(result.sources)}")
    print(f"正文字数: {len(result.text)}")


if __name__ == "__main__":
    main()

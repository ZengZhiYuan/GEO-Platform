from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_dockerfile_uses_cn_mirrors_and_preserves_dependency_cache_layer():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "ARG APT_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/debian" in dockerfile
    assert "ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple" in dockerfile
    assert "ARG PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn" in dockerfile
    assert "PIP_INDEX_URL=${PIP_INDEX_URL}" in dockerfile
    assert "PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST}" in dockerfile
    assert "--prefer-binary" in dockerfile

    requirements_copy = dockerfile.index("COPY backend/requirements.txt backend/requirements.txt")
    source_copy = dockerfile.index("COPY backend backend")
    assert requirements_copy < source_copy


def test_dockerignore_keeps_build_context_small():
    dockerignore_path = ROOT / ".dockerignore"

    assert dockerignore_path.exists()
    dockerignore = dockerignore_path.read_text(encoding="utf-8")

    assert ".git" in dockerignore
    assert "backend/.venv" in dockerignore
    assert "frontend/node_modules" in dockerignore
    assert "data/" in dockerignore


def test_compose_overrides_build_mirrors_with_aliyun_defaults():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert 'APT_MIRROR: "${APT_MIRROR:-https://mirrors.aliyun.com/debian}"' in compose
    assert (
        'APT_SECURITY_MIRROR: '
        '"${APT_SECURITY_MIRROR:-https://mirrors.aliyun.com/debian-security}"'
    ) in compose
    assert 'PIP_INDEX_URL: "${PIP_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple}"' in compose
    assert 'PIP_TRUSTED_HOST: "${PIP_TRUSTED_HOST:-mirrors.aliyun.com}"' in compose

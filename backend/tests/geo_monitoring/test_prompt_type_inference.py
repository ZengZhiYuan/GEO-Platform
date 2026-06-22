from app.geo_monitoring.services.prompt_type_inference import infer_prompt_type


def test_infer_recommendation_prompt_type():
    assert (
        infer_prompt_type("推荐国内有哪些值得看的文旅演艺项目？", core_keyword="文旅演艺")
        == "recommendation"
    )


def test_infer_comparison_prompt_type():
    assert (
        infer_prompt_type("宋城演艺和只有河南哪个更好？", core_keyword="文旅")
        == "comparison"
    )


def test_infer_brand_visibility_prompt_type():
    assert (
        infer_prompt_type("宋城演艺是做什么的？", brand_name="宋城演艺", core_keyword="文旅演艺")
        == "brand_visibility"
    )


def test_infer_generic_prompt_type():
    assert infer_prompt_type("什么是监测平台？", core_keyword="GEO") == "generic"

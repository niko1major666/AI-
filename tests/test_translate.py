from src.data.translate import translate_title


def test_chinese_unchanged():
    assert translate_title("AI算法工程师") == "AI算法工程师"
    assert translate_title("深度学习研发工程师") == "深度学习研发工程师"


def test_exact_match():
    assert translate_title("AI Engineer") == "AI工程师"
    assert translate_title("Data Scientist") == "数据科学家"


def test_word_level():
    assert "工程师" in translate_title("Senior Software Engineer")
    assert translate_title("Backend Engineer") == "后端工程师"


def test_empty():
    assert translate_title("") == ""
    assert translate_title(None) is None

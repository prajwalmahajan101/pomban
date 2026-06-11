from pomban.core.task_input import parse_task_input


def test_plain_title():
    p = parse_task_input("Write the report")
    assert p.title == "Write the report"
    assert p.tags == [] and p.estimate == 0
    assert p.project_name is None and p.sprint_name is None


def test_tags_project_sprint_estimate():
    p = parse_task_input("Wire OAuth @work !v1.0 ~5 #backend #urgent")
    assert p.title == "Wire OAuth"
    assert p.tags == ["backend", "urgent"]
    assert p.tags_csv == "backend,urgent"
    assert p.project_name == "work" and p.sprint_name == "v1.0" and p.estimate == 5


def test_first_project_wins_later_become_title_words():
    p = parse_task_input("ship @a @b feature")
    assert p.project_name == "a"
    assert "@b" in p.title and "feature" in p.title


def test_bad_estimate_stays_a_title_word():
    p = parse_task_input("task ~abc")
    assert p.estimate == 0 and "~abc" in p.title


def test_lone_sigils_are_title_words():
    p = parse_task_input("a # @ ! ~ b")
    assert p.tags == [] and p.project_name is None
    assert p.title == "a # @ ! ~ b"

# How each skill_level option describes the viewer to the model.
AUDIENCES = {
    "5th_grade": (
        "a curious 5th grader (age 10-11) with no scientific background. "
        "Use simple everyday words, short sentences, and fun analogies. "
        "Avoid all jargon. If a technical term is unavoidable, immediately explain it "
        "with a concrete real-world comparison a child would recognise."
    ),
    "10th_grade": (
        "a 10th grade high school student (age 15-16) who has taken basic science and maths. "
        "You can use common scientific terms but explain anything advanced. "
        "Relate ideas to things they have seen in school (algebra, basic physics, biology). "
        "Keep it engaging without over-simplifying."
    ),
    "college": (
        "a college-educated adult or undergraduate with general scientific literacy. "
        "You can use technical terminology, discuss methodology, and include quantitative details. "
        "Assume comfort with maths and scientific reasoning. Prioritise depth and precision."
    ),
}

DEFAULT_AUDIENCE = "a college-educated adult with general scientific literacy."


def audience_for(skill_level):
    return AUDIENCES.get(skill_level, DEFAULT_AUDIENCE)

def qa_prompt(summary, paper_text, question):
    """Follow-up question about a finished video, answered from the paper."""
    return (
        "You are a helpful research assistant. A user has watched a short animated "
        "explainer video about a research paper and has a follow-up question.\n\n"
        "Answer their question clearly and accurately based on the paper content below. "
        "Use the same tone as 3Blue1Brown: direct, warm, curious, and simple. "
        "If the answer isn't in the paper, say so honestly.\n\n"
        "Keep your answer concise (2-4 paragraphs max). Use plain language.\n\n"
        f"PAPER SUMMARY:\n{summary}\n\n"
        f"FULL PAPER TEXT:\n{paper_text}\n\n"
        f"USER QUESTION: {question}"
    )

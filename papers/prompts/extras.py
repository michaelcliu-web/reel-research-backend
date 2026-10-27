def takeaways_prompt(audience, summary):
    """Summary → JSON array of key terms and definitions."""
    return (
        f"Based on the following research paper summary, produce a JSON array of 5-7 key concepts. "
        f"Each entry must have:\n"
        f'  "term": the concept name (2-5 words)\n'
        f'  "definition": a plain-language explanation (1-2 sentences, written for {audience})\n'
        f"Return ONLY a valid JSON array. No markdown, no explanation.\n"
        f'Example: [{{"term": "Neural Network", "definition": "A system loosely inspired by the brain..."}}]\n\n'
        f"Summary:\n{summary}"
    )


def quiz_prompt(audience, summary):
    """Summary → JSON array of multiple-choice questions."""
    return (
        f"Based on the following research paper summary, create a quiz of 3-5 multiple-choice questions "
        f"to test comprehension of the key ideas. Write the questions for {audience}.\n"
        f"Each question must have:\n"
        f'  "question": the question text\n'
        f'  "options": an array of exactly 4 answer strings (do NOT include A/B/C/D prefixes)\n'
        f'  "answer": the 0-based index of the correct option\n'
        f'  "explanation": one sentence explaining why the answer is correct\n'
        f"Return ONLY a valid JSON array. No markdown, no extra text.\n"
        f'Example: [{{"question": "What does a neural network do?", "options": ["Stores data", "Learns patterns", "Manages memory", "Encrypts files"], "answer": 1, "explanation": "Neural networks learn patterns from training data."}}]\n\n'
        f"Summary:\n{summary}"
    )


def suggested_papers_prompt(summary):
    """Summary → JSON array of real papers to read next."""
    return (
        f"Based on the following research paper summary, recommend 3-5 real, published papers "
        f"that a reader should explore next to deepen their understanding of this topic.\n"
        f"Each recommendation must have:\n"
        f'  "title": the full paper title\n'
        f'  "authors": author(s) as a short string (e.g. "LeCun et al." or "Smith & Jones")\n'
        f'  "year": publication year as a number\n'
        f'  "reason": one sentence explaining how it complements or extends this paper\n'
        f"Return ONLY a valid JSON array. No markdown, no extra text.\n"
        f'Example: [{{"title": "Attention Is All You Need", "authors": "Vaswani et al.", "year": 2017, "reason": "Introduces the transformer architecture that this paper builds upon."}}]\n\n'
        f"Summary:\n{summary}"
    )

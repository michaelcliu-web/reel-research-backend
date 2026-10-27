def storyboard_prompt(audience, summary):
    """Summary → JSON array of scenes with narration, visuals and duration."""
    return (
        "You are planning a short animated explainer video for a research paper. "
        f"YOUR AUDIENCE: {audience} Match the narration language and visual complexity to this audience.\n\n"
        "Break the following summary into scenes mirroring the structure of the summary for a 60-120 second vertical video. This should be 1-3 scenes for step 1, 6-8 scenes for step 2, 1-3 scenes for step 3.\n\n"
        "For each scene provide:\n"
        "- narration: Elucidated spoken text for that scene\n"
        "- visuals: A concise description of what to animate, be as descriptive as possible for the best intuitive understanding for the viewer.\n"
        "- specifics: Make sure to be descriptive when explaining the core of the paper. Ground answers int he paper. Try and include raw formulas, mathematics, the science, the change in thinking, and why it works in the animations.\n"
        "- NEVER repeat long formulas, constants, or in speech. ONLY have it on the screen as necessary.\n"
        "- duration: Make sure to be descriptive and create an intuitive understanding when possible, but be sure to keep it to around 60-120 seconds.\n\n"
        f"Reminder: MAKE SURE to follow the instructions in {audience}.\n"
        "Return ONLY a valid JSON array. No markdown, no explanation. Example:\n"
        '[{"scene": 1, "narration": "...", "visuals": "...", "specifics": "...", "duration": 5}]\n\n'
        f"Summary:\n{summary}"
    )

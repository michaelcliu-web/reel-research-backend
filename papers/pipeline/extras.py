import asyncio

from papers.pipeline.llm import ask_json_array
from papers.prompts.extras import takeaways_prompt, quiz_prompt, suggested_papers_prompt


async def generate_extras(audience, summary):
    """Return (key_takeaways, quiz, suggested_papers), generated in parallel; each is [] on failure."""
    return await asyncio.gather(
        ask_json_array(takeaways_prompt(audience, summary)),
        ask_json_array(quiz_prompt(audience, summary)),
        ask_json_array(suggested_papers_prompt(summary)),
    )

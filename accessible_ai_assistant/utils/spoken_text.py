"""Remove common formatting markers from model messages before speech and display."""
import re


def plain_spoken_text(text: str) -> str:
    # Opening fences may include a language name, which is not part of the code.
    text = re.sub(r"(?m)^[ \t]*(?:`{3,}|~{3,}|´{3,})[\w+-]*[ \t]*$", "", text)
    text = re.sub(r"(?:`{3,}|´{3,})[a-zA-Z][\w+-]*[ \t]+(?=[^\n]*(?:`{3,}|´{3,}))", "", text)
    text = re.sub(r"`+|´{2,}", "", text)
    text = re.sub(r"!?\[([^\]\n]+)\]\([^\s)]+\)", r"\1", text)
    text = re.sub(r"(?m)^[ \t]*(?:#{1,6}|>+|[-*+•])[ \t]+", "", text)
    text = re.sub(r"(?m)^[ \t]*(?:-{3,}|\*{3,}|_{3,})[ \t]*$", "", text)
    text = re.sub(r"(?<!\w)(\*\*\*|\*\*|\*|__|_|~~)(?=\S)([^\n]+?)(?<=\S)\1(?!\w)", r"\2", text)
    return text.strip()

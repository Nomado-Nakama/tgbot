"""
Populate a couple of demo rows so local dev & CI aren't empty.
Run once: `python -m scripts.seed_demo`
"""
import asyncio

from src.bot.db import execute


async def main() -> None:
    await execute(
        """
        INSERT INTO content (parent_id, title, body, ord) VALUES
          (NULL, 'Европа', NULL, 0),
          (NULL, 'Азия',   NULL, 1),
          ((SELECT id FROM content WHERE title='Европа'), 'Франция', 'Текст о Франции', 0),
          ((SELECT id FROM content WHERE title='Европа'), 'Испания', 'Текст об Испании', 1);
        """
    )
    print("✅ Demo content inserted")


if __name__ == "__main__":
    asyncio.run(main())

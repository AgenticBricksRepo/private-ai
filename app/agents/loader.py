"""Agent .md file parser."""

import frontmatter


def parse_agent_file(filepath: str) -> dict:
    """Parse an agent markdown file into a dict with frontmatter + body."""
    with open(filepath) as f:
        post = frontmatter.load(f)
    return {
        "name": post.get("name", "Unnamed Agent"),
        "description": post.get("description", ""),
        "mode": post.get("mode", "interactive"),
        "trigger_config": {
            "type": post["trigger"]["type"],
            "cron": post["trigger"].get("cron"),
        } if post.get("trigger") else None,
        "tools": post.get("tools", []),
        "connectors": post.get("connectors", []),
        "folders": post.get("folders", []),
        "requires_confirmation": post.get("requires_confirmation", True),
        "prompt_md": post.content,
    }

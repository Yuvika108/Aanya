#!/usr/bin/env python3
"""
✦ AANYA AI — OpenAI Model Diagnostic & Playground ✦
An aesthetically styled terminal interface to test OpenAI completions with Aanya's persona.
"""

import os
import re
import sys
import time
import textwrap
from config import apikey

# ─────────────────────────────────────────────
#  ANSI Palette & Visual Styling
# ─────────────────────────────────────────────
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    ITALIC  = "\033[3m"

    WHITE   = "\033[97m"
    CYAN    = "\033[96m"
    MAGENTA = "\033[95m"
    BLUE    = "\033[94m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    GREY    = "\033[90m"


W = 74
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

def vis_len(s: str) -> int:
    """Return visible character length excluding ANSI escape codes."""
    return len(ANSI_RE.sub("", s))


def render_banner():
    print(f"\n{C.CYAN}╭" + "─" * (W - 2) + f"╮{C.RESET}")
    title = "✦  AANYA AI  —  OpenAI Model Diagnostic  ✦"
    print(f"{C.CYAN}│{C.BOLD}{C.MAGENTA}{title:^{W-2}}{C.RESET}{C.CYAN}│{C.RESET}")
    sub = "Personal Voice & AI Assistant for Srishti Mishra"
    print(f"{C.CYAN}│{C.DIM}{C.WHITE}{sub:^{W-2}}{C.RESET}{C.CYAN}│{C.RESET}")
    print(f"{C.CYAN}╰" + "─" * (W - 2) + f"╯{C.RESET}\n")


def render_meta(model: str, user_name: str, query: str):
    title = "SESSION METADATA"
    header = f"┌─ {C.BOLD}{C.CYAN}{title}{C.RESET}{C.GREY} " + "─" * max(0, W - 5 - len(title)) + "┐"
    print(f"{C.GREY}{header}{C.RESET}")

    items = [
        (f"{C.BOLD}Model:{C.RESET}", f"{C.GREEN}{model}{C.RESET}"),
        (f"{C.BOLD}Assistant:{C.RESET}", f"{C.MAGENTA}Aanya{C.RESET} {C.GREY}(for {user_name}){C.RESET}"),
        (f"{C.BOLD}Prompt:{C.RESET}", f"{C.YELLOW}\"{query}\"{C.RESET}"),
    ]
    for label, val in items:
        raw_text = f"{label}  {val}"
        pad = " " * max(0, W - 4 - vis_len(raw_text))
        print(f"{C.GREY}│{C.RESET}  {raw_text}{pad}{C.GREY}│{C.RESET}")

    print(f"{C.GREY}└" + "─" * (W - 2) + f"┘{C.RESET}\n")


def render_card(title: str, text: str, border_color=C.CYAN, title_color=C.MAGENTA):
    title_display = f"✦ {title}"
    header = f"╭─ {C.BOLD}{title_color}{title_display}{C.RESET}{border_color} " + "─" * max(0, W - 5 - vis_len(title_display)) + "╮"
    print(f"{border_color}{header}{C.RESET}")

    paragraphs = text.strip().split("\n")
    for p in paragraphs:
        if not p.strip():
            print(f"{border_color}│{C.RESET}" + " " * (W - 2) + f"{border_color}│{C.RESET}")
            continue

        wrapped = textwrap.wrap(p, width=W - 6)
        for line in wrapped:
            formatted = line
            # Highlight bullets and numbered lists
            if formatted.startswith("- ") or formatted.startswith("• "):
                formatted = f"{C.CYAN}•{C.RESET} {C.WHITE}" + formatted[2:] + C.RESET
            elif re.match(r"^\d+\.\s", formatted):
                m = re.match(r"^(\d+\.)\s(.*)", formatted)
                if m:
                    formatted = f"{C.YELLOW}{m.group(1)}{C.RESET} {C.WHITE}{m.group(2)}{C.RESET}"
            else:
                formatted = f"{C.WHITE}{formatted}{C.RESET}"

            pad = " " * max(0, W - 4 - vis_len(formatted))
            print(f"{border_color}│{C.RESET}  {formatted}{pad}{border_color}│{C.RESET}")

    print(f"{border_color}╰" + "─" * (W - 2) + f"╯{C.RESET}")


def render_footer(duration: float, status="Success", note=""):
    print(f"\n{C.GREY}  › Duration: {C.WHITE}{duration:.2f}s{C.GREY}  •  Status: {C.GREEN}● {status}{C.GREY}  {note}{C.RESET}\n")


def render_warning(title: str, message: str, tips: list[str]):
    header = f"╭─ [!] {C.BOLD}{C.YELLOW}{title}{C.RESET}{C.YELLOW} " + "─" * max(0, W - 9 - len(title)) + "╮"
    print(f"{C.YELLOW}{header}{C.RESET}")
    print(f"{C.YELLOW}│{C.RESET}" + " " * (W - 2) + f"{C.YELLOW}│{C.RESET}")

    for line in textwrap.wrap(message, width=W - 6):
        pad = " " * max(0, W - 4 - len(line))
        print(f"{C.YELLOW}│{C.RESET}  {C.WHITE}{line}{C.RESET}{pad}{C.YELLOW}│{C.RESET}")

    print(f"{C.YELLOW}│{C.RESET}" + " " * (W - 2) + f"{C.YELLOW}│{C.RESET}")
    steps_title = "Quick Setup Steps:"
    print(f"{C.YELLOW}│{C.RESET}  {C.BOLD}{C.CYAN}{steps_title}{C.RESET}" + " " * (W - 4 - len(steps_title)) + f"{C.YELLOW}│{C.RESET}")

    for tip in tips:
        pad = " " * max(0, W - 6 - len(tip))
        print(f"{C.YELLOW}│{C.RESET}   {C.GREY}→{C.RESET} {C.WHITE}{tip}{C.RESET}{pad}{C.YELLOW}│{C.RESET}")

    print(f"{C.YELLOW}│{C.RESET}" + " " * (W - 2) + f"{C.YELLOW}│{C.RESET}")
    print(f"{C.YELLOW}╰" + "─" * (W - 2) + f"╯{C.RESET}\n")


# ─────────────────────────────────────────────
#  Main Execution
# ─────────────────────────────────────────────
def main():
    render_banner()

    model_name = "gpt-4o-mini"
    user_name = "Srishti Mishra"
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Create a study plan for today."

    render_meta(model_name, user_name, query)

    # 1. Check if OpenAI API key is configured
    if not apikey:
        render_warning(
            title="OPENAI_API_KEY Missing in Configuration",
            message="No OpenAI API key was detected in your .env or environment variables. Live completion was skipped to avoid an unhandled crash.",
            tips=[
                "Add your key to /Users/skmishra19/Aanya/.env: OPENAI_API_KEY=sk-...",
                "Or in your terminal: export OPENAI_API_KEY=\"your_key_here\"",
                "Run again: python openaitest.py"
            ]
        )

        # Render simulated response preview
        print(f"{C.DIM}{C.GREY}  [Displaying Simulated Aanya Persona Preview]{C.RESET}\n")
        time.sleep(0.3)
        start_time = time.time()
        simulated_response = (
            f"Good morning, {user_name}! Here is a focused study plan tailored for your goals today:\n\n"
            "• 09:00 AM – 11:00 AM: Deep Focus — Data Structures & System Architecture\n"
            "• 11:15 AM – 01:00 PM: Hands-on Problem Solving & Algorithm Practice\n"
            "• 02:00 PM – 03:30 PM: Aanya Project Enhancements & API Optimization\n"
            "• 03:45 PM – 04:30 PM: Code Review & Documentation Retention\n"
            "• 04:30 PM – 05:00 PM: Daily Summary, Next-Day Prep & Mindful Wind-Down\n\n"
            "◆ Pro-Tip: Take a 5-minute breather between deep work sessions. You've got this!"
        )
        render_card("Aanya's Response (Preview)", simulated_response, border_color=C.CYAN)
        render_footer(time.time() - start_time, status="Simulated Preview", note="(set key for live API)")
        return

    # 2. Live API Execution
    try:
        from openai import OpenAI
        client = OpenAI(api_key=apikey)

        print(f"  {C.CYAN}◈ Connecting to OpenAI API ({model_name})...{C.RESET}")
        start_time = time.time()

        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": f"You are Aanya, a helpful, charming, and organized personal AI assistant for {user_name}."
                },
                {
                    "role": "user",
                    "content": query
                }
            ],
            temperature=0.7,
            max_tokens=350
        )
        duration = time.time() - start_time
        reply_text = response.choices[0].message.content

        # Clear connecting line
        sys.stdout.write("\033[F\033[K")
        sys.stdout.flush()

        render_card("Aanya's Response", reply_text, border_color=C.CYAN)
        usage = getattr(response, "usage", None)
        tokens_info = f"• {usage.total_tokens} tokens" if usage else ""
        render_footer(duration, status="Online", note=tokens_info)

    except Exception as exc:
        render_warning(
            title="OpenAI API Error",
            message=f"Failed to communicate with OpenAI: {exc}",
            tips=[
                "Verify that your API key is valid and has active quota.",
                "Check your network connection or firewall settings.",
                "Inspect OpenAI service status if errors persist."
            ]
        )


if __name__ == "__main__":
    main()
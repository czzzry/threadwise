from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs" / "assets" / "marketing" / "readme-storyboard"

FONT_REGULAR = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_SERIF_BOLD = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"

INK = "#20232A"
MUTED = "#68707D"
FAINT = "#9299A5"
LINE = "#D9DDE5"
LINE_SOFT = "#EDF0F4"
CANVAS = "#F4F5F7"
WHITE = "#FFFFFF"
PURPLE = "#6258F5"
PURPLE_SOFT = "#EFEEFF"
GREEN = "#157A56"
GREEN_SOFT = "#E5F6EE"
BLUE = "#2D68B2"
BLUE_SOFT = "#EAF2FF"
ORANGE = "#925112"
ORANGE_SOFT = "#FFF0DF"
YELLOW = "#F6C552"


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, size=size)


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, fill: str, *, outline: str | None = None, width: int = 1) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text(draw: ImageDraw.ImageDraw, point: tuple[int, int], value: str, size: int, fill: str = INK, *, bold: bool = False, anchor: str | None = None) -> None:
    draw.text(point, value, font=font(size, bold=bold), fill=fill, anchor=anchor)


def wrapped_text(
    draw: ImageDraw.ImageDraw,
    point: tuple[int, int],
    value: str,
    size: int,
    fill: str,
    max_width: int,
    *,
    bold: bool = False,
    line_gap: int = 5,
) -> int:
    words = value.split()
    lines: list[str] = []
    current = ""
    typeface = font(size, bold=bold)
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=typeface)[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    x, y = point
    line_height = size + line_gap
    for index, line in enumerate(lines):
        draw.text((x, y + index * line_height), line, font=typeface, fill=fill)
    return y + len(lines) * line_height


def add_shadow(image: Image.Image, box: tuple[int, int, int, int], radius: int = 22, opacity: int = 36) -> None:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(layer)
    x1, y1, x2, y2 = box
    shadow_draw.rounded_rectangle((x1 + 2, y1 + 10, x2 + 2, y2 + 10), radius=12, fill=(25, 31, 45, opacity))
    image.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius)))


def build_refined_mark() -> Image.Image:
    scale = 4
    mark = Image.new("RGBA", (256 * scale, 256 * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(mark)
    draw.rounded_rectangle(
        (10 * scale, 10 * scale, 246 * scale, 246 * scale),
        radius=42 * scale,
        fill=YELLOW,
        outline=INK,
        width=8 * scale,
    )

    # Rebuild the thread-and-envelope glyph as clean vector-like geometry. The
    # inherited raster asset has a lovely idea but becomes visibly ragged at UI size.
    serif = ImageFont.truetype(FONT_SERIF_BOLD, size=122 * scale)
    draw.text((104 * scale, 82 * scale), "T", font=serif, fill=INK, anchor="mm")
    stroke = 6 * scale

    def cubic(start: tuple[float, float], control_a: tuple[float, float], control_b: tuple[float, float], end: tuple[float, float]) -> list[tuple[int, int]]:
        points: list[tuple[int, int]] = []
        for step in range(25):
            amount = step / 24
            inverse = 1 - amount
            x = inverse**3 * start[0] + 3 * inverse**2 * amount * control_a[0] + 3 * inverse * amount**2 * control_b[0] + amount**3 * end[0]
            y = inverse**3 * start[1] + 3 * inverse**2 * amount * control_a[1] + 3 * inverse * amount**2 * control_b[1] + amount**3 * end[1]
            points.append((round(x * scale), round(y * scale)))
        return points

    thread_points = cubic((105, 130), (83, 141), (57, 145), (58, 168))
    thread_points += cubic((58, 168), (61, 194), (105, 191), (149, 190))[1:]
    draw.line(
        thread_points,
        fill=INK,
        width=stroke,
        joint="curve",
    )
    envelope = (146 * scale, 157 * scale, 216 * scale, 202 * scale)
    draw.rounded_rectangle(envelope, radius=3 * scale, fill=YELLOW, outline=INK, width=5 * scale)
    draw.line(
        (
            149 * scale,
            160 * scale,
            181 * scale,
            184 * scale,
            213 * scale,
            160 * scale,
        ),
        fill=INK,
        width=4 * scale,
        joint="curve",
    )
    return mark.resize((256, 256), Image.Resampling.LANCZOS)


def paste_mark(image: Image.Image, mark: Image.Image, box: tuple[int, int, int, int]) -> None:
    x1, y1, x2, y2 = box
    resized = mark.resize((x2 - x1, y2 - y1), Image.Resampling.LANCZOS)
    image.alpha_composite(resized, (x1, y1))


def draw_cursor(image: Image.Image, x: int, y: int, size: int = 38) -> None:
    render_scale = 4
    cursor = Image.new("RGBA", (size * render_scale, size * render_scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(cursor)
    scale = size * render_scale / 38
    points = [
        (3 * scale, 2 * scale),
        (5 * scale, 31 * scale),
        (12 * scale, 24 * scale),
        (19 * scale, 36 * scale),
        (25 * scale, 32 * scale),
        (18 * scale, 21 * scale),
        (29 * scale, 20 * scale),
    ]
    draw.polygon(points, fill=WHITE, outline=INK)
    draw.line(points + [points[0]], fill=INK, width=max(2, int(2.2 * scale)), joint="curve")
    cursor = cursor.resize((size, size), Image.Resampling.LANCZOS)
    image.alpha_composite(cursor, (x, y))


def draw_label(draw: ImageDraw.ImageDraw, x: int, y: int, value: str, tone: str = "blue", *, emphasized: bool = False) -> int:
    palette = {
        "blue": (BLUE_SOFT, BLUE),
        "purple": (PURPLE_SOFT, "#5046B7"),
        "green": (GREEN_SOFT, GREEN),
        "orange": (ORANGE_SOFT, ORANGE),
    }
    background, foreground = palette[tone]
    label_font = font(14, bold=True)
    width = draw.textbbox((0, 0), value, font=label_font)[2] + 22
    rounded(draw, (x, y, x + width, y + 28), 6, background, outline=PURPLE if emphasized else None, width=2)
    draw.text((x + 11, y + 7), value, font=label_font, fill=foreground)
    return width


def draw_email_row(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    sender: str,
    subject: str,
    timestamp: str,
    labels: list[tuple[str, str]],
    *,
    selected: bool = False,
    newly_labeled: bool = False,
    needs_review: bool = False,
) -> None:
    x1, y1, x2, y2 = box
    draw.rectangle(box, fill="#F5F4FF" if selected else WHITE)
    draw.line((x1, y2, x2, y2), fill=LINE_SOFT, width=1)
    if selected:
        draw.rectangle((x1, y1, x1 + 4, y2), fill=PURPLE)
    text(draw, (x1 + 18, y1 + 14), sender, 18, bold=True)
    text(draw, (x2 - 17, y1 + 17), timestamp, 13, FAINT, anchor="ra")
    max_subject = max(16, int((x2 - x1 - 48) / 9.5))
    display_subject = subject if len(subject) <= max_subject else subject[: max_subject - 1] + "…"
    text(draw, (x1 + 18, y1 + 43), display_subject, 16, "#535B67")
    label_x = x1 + 18
    for index, (value, tone) in enumerate(labels):
        label_x += draw_label(draw, label_x, y1 + 69, value, tone, emphasized=newly_labeled and index == 0) + 7
    if needs_review:
        draw.ellipse((x1 + 19, y1 + 74, x1 + 29, y1 + 84), fill=PURPLE)


def draw_panel(image: Image.Image, panel_box: tuple[int, int, int, int], mark: Image.Image, *, next_email: bool = False) -> None:
    draw = ImageDraw.Draw(image)
    x1, y1, x2, y2 = panel_box
    draw.rectangle(panel_box, fill=WHITE)
    draw.line((x1, y1, x1, y2), fill="#C9CED8", width=2)
    draw.line((x1, y1 + 64, x2, y1 + 64), fill=LINE, width=1)
    paste_mark(image, mark, (x1 + 18, y1 + 14, x1 + 55, y1 + 51))
    text(draw, (x1 + 67, y1 + 21), "Threadwise", 20, bold=True)
    text(draw, (x1 + 191, y1 + 24), "Ready", 15, MUTED)
    text(draw, (x2 - 21, y1 + 28), "−", 24, MUTED, anchor="ma")

    content_x = x1 + 22
    content_w = x2 - x1 - 44
    subject = "Your Actions workflow completed" if next_email else "Your Google data is ready to download"
    sender = "GitHub" if next_email else "Google"
    index = "2 of 3" if next_email else "1 of 3"
    display_subject = subject if len(subject) < 35 else subject[:34] + "…"
    text(draw, (content_x, y1 + 89), display_subject, 17, bold=True)
    text(draw, (content_x, y1 + 115), sender, 14, MUTED)
    text(draw, (x2 - 22, y1 + 93), index, 14, MUTED, anchor="ra")
    draw.line((content_x, y1 + 144, x2 - 22, y1 + 144), fill=LINE_SOFT, width=1)
    rounded(draw, (content_x, y1 + 154, x2 - 22, y1 + 158), 2, "#E3E6EB")
    draw.rectangle((content_x, y1 + 154, content_x + (208 if next_email else 105), y1 + 158), fill=PURPLE)

    title = "Personal" if next_email else "Personal + Account"
    subtitle = (
        "A notification from one of your personal development projects."
        if next_email
        else "Threadwise wants your confirmation before it remembers this rare case."
    )
    text(draw, (content_x, y1 + 188), title, 28, bold=True)
    subtitle_bottom = wrapped_text(draw, (content_x, y1 + 226), subtitle, 16, MUTED, content_w, line_gap=6)
    pill_y = subtitle_bottom + 8
    pill_x = content_x
    pill_x += draw_label(draw, pill_x, pill_y, "Personal", "green") + 8
    if not next_email:
        draw_label(draw, pill_x, pill_y, "Account", "purple")

    reason_y = pill_y + 44
    reason_h = 116 if next_email else 136
    rounded(draw, (content_x, reason_y, x2 - 22, reason_y + reason_h), 10, "#F4F5F7")
    text(draw, (content_x + 14, reason_y + 14), "Ready for the next decision" if next_email else "Why this, specifically", 16, bold=True)
    reason = (
        "The previous labels are applying in the background, so review never has to wait."
        if next_email
        else "This is a one-time archive notice. The lesson applies to this kind of Google message, not every account email from Google."
    )
    wrapped_text(draw, (content_x + 14, reason_y + 42), reason, 15, "#4F5662", content_w - 28, line_gap=5)

    facts_y = reason_y + reason_h + 17
    draw.line((content_x, facts_y, x2 - 22, facts_y), fill=LINE_SOFT, width=1)
    for label, value, row in (
        ("Inbox", "Keep visible", 0),
        ("Scope", "This email only", 1),
    ):
        row_y = facts_y + row * 47
        text(draw, (content_x, row_y + 15), label, 15, MUTED)
        text(draw, (x2 - 22, row_y + 15), value, 15, INK, bold=True, anchor="ra")
        draw.line((content_x, row_y + 46, x2 - 22, row_y + 46), fill=LINE_SOFT, width=1)

    cta_y = facts_y + 111
    rounded(draw, (content_x, cta_y, x2 - 22, cta_y + 54), 8, PURPLE)
    cta = "Apply Personal · Next" if next_email else "Apply Personal + Account · Next"
    text(draw, ((content_x + x2 - 22) // 2, cta_y + 28), cta, 16, WHITE, bold=True, anchor="mm")
    if next_email:
        receipt_y = cta_y + 70
        rounded(draw, (content_x, receipt_y, x2 - 22, receipt_y + 48), 8, GREEN_SOFT)
        draw.ellipse((content_x + 13, receipt_y + 18, content_x + 23, receipt_y + 28), fill=GREEN)
        text(draw, (content_x + 32, receipt_y + 16), "Previous labels applied in the background", 13, GREEN, bold=True)
    else:
        text(draw, (content_x, cta_y + 75), "⌄  How Threadwise understood this", 14, MUTED, bold=True)


def draw_browser_scene(
    mark: Image.Image,
    *,
    provider: str = "gmail",
    labels_applied: bool = False,
    panel_open: bool = False,
    next_email: bool = False,
    cursor: str | None = None,
) -> Image.Image:
    image = Image.new("RGBA", (1600, 900), CANVAS)
    add_shadow(image, (58, 50, 1542, 850), radius=22, opacity=42)
    draw = ImageDraw.Draw(image)
    rounded(draw, (58, 50, 1542, 850), 12, WHITE, outline="#C7CCD5", width=2)
    draw.rectangle((60, 52, 1540, 108), fill="#F8F9FB")
    draw.line((60, 108, 1540, 108), fill=LINE, width=1)
    for index in range(3):
        draw.ellipse((82 + index * 24, 75, 94 + index * 24, 87), fill="#C5CBD4")
    rounded(draw, (175, 67, 720, 94), 6, WHITE, outline="#E1E4E9")
    address = "mail.proton.me · Inbox" if provider == "proton" else "mail.google.com · Inbox"
    text(draw, (191, 74), address, 13, FAINT)
    text(draw, (1500, 79), "☆   ⋮", 18, FAINT, anchor="ra")

    app_y1, app_y2 = 109, 848
    nav_w = 205
    nav_x2 = 60 + nav_w
    draw.rectangle((60, app_y1, nav_x2, app_y2), fill="#F8F7FF" if provider == "proton" else "#FAFBFC")
    draw.line((nav_x2, app_y1, nav_x2, app_y2), fill=LINE, width=1)
    provider_color = "#6546F4" if provider == "proton" else "#E85A52"
    rounded(draw, (86, 137, 113, 164), 6, provider_color)
    text(draw, (124, 141), "Proton Mail" if provider == "proton" else "Gmail", 20, "#3F4652", bold=True)
    rounded(draw, (82, 188, 237, 229), 8, "#6546F4" if provider == "proton" else "#4F6DC9")
    text(draw, (159, 209), "Compose", 15, WHITE, bold=True, anchor="mm")
    nav_labels = ("Inbox", "Drafts", "Sent", "Archive") if provider == "proton" else ("Inbox", "Starred", "Sent", "Archive")
    for index, label in enumerate(nav_labels):
        item_y = 254 + index * 45
        if index == 0:
            rounded(draw, (78, item_y - 7, 241, item_y + 28), 7, "#EDF0F4")
        text(draw, (98, item_y), label, 16, "#323944" if index == 0 else MUTED, bold=index == 0)
    text(draw, (224, 254), "18", 14, FAINT, anchor="ra")

    list_x1 = nav_x2
    list_w = 485
    list_x2 = list_x1 + list_w
    draw.line((list_x2, app_y1, list_x2, app_y2), fill=LINE, width=1)
    draw.rectangle((list_x1, app_y1, list_x2, app_y1 + 58), fill=WHITE)
    draw.line((list_x1, app_y1 + 58, list_x2, app_y1 + 58), fill=LINE_SOFT, width=1)
    text(draw, (list_x1 + 20, app_y1 + 20), "Inbox", 19, bold=True)
    text(draw, (list_x2 - 19, app_y1 + 22), "↻   ···", 16, FAINT, anchor="ra")

    rows = [
        ("Stripe", "Your receipt for Threadwise Cloud", "9:42 AM", [("Receipt", "blue"), ("Account", "purple")]),
        ("Google", "Your Google data is ready to download", "9:18 AM", []),
        ("GitHub", "Your Actions workflow completed", "8:57 AM", [("Personal", "green")]),
        ("Figma", "A new comment on your file", "Yesterday", [("Work", "blue")]),
        ("Spaceship", "Please verify your account", "Yesterday", [("Account", "purple")]),
    ]
    row_y = app_y1 + 58
    row_h = 114
    for index, (sender, subject, timestamp, labels) in enumerate(rows):
        draw_email_row(
            draw,
            (list_x1, row_y + index * row_h, list_x2, row_y + (index + 1) * row_h),
            sender,
            subject,
            timestamp,
            labels if (labels_applied or index != 0) else [],
            selected=index == (2 if next_email else 1),
            newly_labeled=labels_applied and index == 0,
            needs_review=index == 1 and not next_email,
        )

    message_x1 = list_x2
    draw.rectangle((message_x1, app_y1, 1540, app_y2), fill=WHITE)
    sender = "GitHub <notifications@github.com>" if next_email else "Google <noreply@google.com>"
    subject = "Your Actions workflow completed" if next_email else "Your Google data is ready to download"
    timestamp = "8:57 AM" if next_email else "9:18 AM"
    text(draw, (message_x1 + 34, app_y1 + 38), sender, 15, MUTED)
    wrapped_text(draw, (message_x1 + 34, app_y1 + 76), subject, 28, INK, 580, bold=True, line_gap=7)
    text(draw, (message_x1 + 34, app_y1 + 151), f"To you · {timestamp}", 14, FAINT)
    draw.line((message_x1 + 34, app_y1 + 189, 1505, app_y1 + 189), fill=LINE_SOFT, width=1)
    for index, width in enumerate((610, 565, 630, 420)):
        rounded(draw, (message_x1 + 34, app_y1 + 232 + index * 32, message_x1 + 34 + width, app_y1 + 241 + index * 32), 4, "#EEF1F4")
    rounded(draw, (message_x1 + 34, app_y1 + 390, message_x1 + 346, app_y1 + 429), 7, "#F4F5F7")
    text(draw, (message_x1 + 49, app_y1 + 401), "Your archive is ready until August 27", 14, MUTED)

    launcher_box = (1470, 129, 1524, 183)
    if not panel_open:
        paste_mark(image, mark, launcher_box)
    else:
        draw_panel(image, (1090, 109, 1540, 848), mark, next_email=next_email)
    if cursor == "launcher":
        draw_cursor(image, 1460, 165, 34)
    elif cursor == "cta":
        draw_cursor(image, 1372, 709, 42)
    return image.convert("RGB")


def crop_level(image: Image.Image, box: tuple[int, int, int, int], size: tuple[int, int] = (1600, 900)) -> Image.Image:
    return image.crop(box).resize(size, Image.Resampling.LANCZOS)


def draw_provider_parity(mark: Image.Image) -> Image.Image:
    image = Image.new("RGBA", (1600, 900), CANVAS)
    draw = ImageDraw.Draw(image)
    text(draw, (80, 68), "Same Threadwise. Your inbox stays yours.", 42, bold=True)
    text(draw, (80, 126), "The host changes. The interaction, reasoning, and controls do not.", 21, MUTED)
    gmail = draw_browser_scene(mark, provider="gmail", labels_applied=True, panel_open=True)
    proton = draw_browser_scene(mark, provider="proton", labels_applied=True, panel_open=True)
    gmail_crop = gmail.crop((180, 54, 1545, 848)).resize((700, 600), Image.Resampling.LANCZOS)
    proton_crop = proton.crop((180, 54, 1545, 848)).resize((700, 600), Image.Resampling.LANCZOS)
    add_shadow(image, (60, 200, 760, 800))
    add_shadow(image, (840, 200, 1540, 800))
    rounded(draw, (60, 187, 760, 803), 10, WHITE, outline="#CBD0D8", width=2)
    rounded(draw, (840, 187, 1540, 803), 10, WHITE, outline="#CBD0D8", width=2)
    image.paste(gmail_crop, (60, 203))
    image.paste(proton_crop, (840, 203))
    rounded(draw, (84, 162, 183, 200), 7, WHITE, outline="#CBD0D8")
    text(draw, (133, 181), "Gmail", 15, INK, bold=True, anchor="mm")
    rounded(draw, (864, 162, 1001, 200), 7, WHITE, outline="#CBD0D8")
    text(draw, (932, 181), "Proton Mail", 15, INK, bold=True, anchor="mm")
    return image.convert("RGB")


def draw_review_sequence(mark: Image.Image) -> Image.Image:
    image = Image.new("RGBA", (1600, 900), CANVAS)
    draw = ImageDraw.Draw(image)
    text(draw, (80, 68), "One decision. Then you are already moving.", 42, bold=True)
    text(draw, (80, 126), "Threadwise loads the next email immediately and finishes the previous write in the background.", 21, MUTED)

    decision = draw_browser_scene(mark, labels_applied=True, panel_open=True, cursor="cta")
    next_email = draw_browser_scene(mark, labels_applied=True, panel_open=True, next_email=True)
    decision_crop = decision.crop((960, 96, 1542, 848)).resize((600, 650), Image.Resampling.LANCZOS)
    next_crop = next_email.crop((960, 96, 1542, 848)).resize((600, 650), Image.Resampling.LANCZOS)

    add_shadow(image, (90, 196, 690, 846), radius=18, opacity=30)
    add_shadow(image, (910, 196, 1510, 846), radius=18, opacity=30)
    rounded(draw, (90, 196, 690, 846), 8, WHITE, outline="#CBD0D8", width=2)
    rounded(draw, (910, 196, 1510, 846), 8, WHITE, outline="#CBD0D8", width=2)
    image.paste(decision_crop, (90, 196))
    image.paste(next_crop, (910, 196))

    rounded(draw, (112, 174, 202, 212), 7, WHITE, outline="#CBD0D8")
    text(draw, (157, 193), "DECIDE", 13, INK, bold=True, anchor="mm")
    rounded(draw, (932, 174, 1054, 212), 7, WHITE, outline="#CBD0D8")
    text(draw, (993, 193), "NEXT EMAIL", 13, INK, bold=True, anchor="mm")
    draw.line((734, 520, 855, 520), fill=PURPLE, width=5)
    draw.polygon(((855, 520), (836, 507), (836, 533)), fill=PURPLE)
    return image.convert("RGB")


def place_story_image(board: Image.Image, asset: Image.Image, box: tuple[int, int, int, int]) -> None:
    x1, y1, x2, y2 = box
    width, height = x2 - x1, y2 - y1
    fitted = asset.copy()
    fitted.thumbnail((width, height), Image.Resampling.LANCZOS)
    x = x1 + (width - fitted.width) // 2
    y = y1 + (height - fitted.height) // 2
    board.paste(fitted, (x, y))


def draw_contact_sheet(mark: Image.Image, assets: dict[str, Image.Image]) -> Image.Image:
    board = Image.new("RGBA", (1800, 5550), CANVAS)
    draw = ImageDraw.Draw(board)
    paste_mark(board, mark, (88, 78, 146, 136))
    text(draw, (166, 84), "Threadwise", 28, bold=True)
    text(draw, (88, 176), "Your inbox, quietly sorted.", 70, bold=True)
    wrapped_text(
        draw,
        (92, 276),
        "Threadwise labels routine mail in the background. When your judgment matters, open the same focused companion in Gmail or Proton Mail, make one decision, and move on.",
        27,
        MUTED,
        1320,
        line_gap=10,
    )
    rounded(draw, (1438, 86, 1712, 136), 8, WHITE, outline="#C9CED8")
    text(draw, (1575, 111), "QUALITY-BAR BOARD", 14, INK, bold=True, anchor="mm")

    sections = [
        ("01", "Hero", "Quiet by default", "Open with the whole inbox and one small Threadwise mark. The product feels additive, not like a replacement email client.", "quiet"),
        ("02", "Proof", "Routine mail is already handled", "Show labels appearing in place. No modal, dashboard, or second inbox interrupts the user.", "labels"),
        ("03", "Interaction", "Open only when judgment matters", "Use one level push-in. The inbox remains visible while the current Threadwise panel explains a rare decision.", "open"),
        ("04", "Trust", "One clear decision, then next", "Make the reasoning narrow and human-readable. The next email loads immediately while the write finishes in the background.", "sequence"),
        ("05", "Parity", "The same Threadwise in both inboxes", "End on equal Gmail and Proton Mail frames. Provider identity changes; Threadwise does not.", "parity"),
    ]
    section_y = 440
    for number, kicker, title_value, body, asset_key in sections:
        text(draw, (90, section_y + 5), number, 18, PURPLE, bold=True)
        text(draw, (148, section_y + 5), kicker.upper(), 16, MUTED, bold=True)
        text(draw, (90, section_y + 40), title_value, 39, bold=True)
        wrapped_text(draw, (90, section_y + 96), body, 21, MUTED, 1470, line_gap=7)
        place_story_image(board, assets[asset_key], (90, section_y + 170, 1710, section_y + 980))
        section_y += 990

    rounded(draw, (90, 5425, 1710, 5510), 10, INK)
    text(draw, (900, 5468), "Clear threads. Better inbox.", 25, WHITE, bold=True, anchor="mm")
    return board.convert("RGB")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    mark = build_refined_mark()
    mark.save(OUTPUT_DIR / "threadwise-mark-refined.png")

    quiet = draw_browser_scene(mark, labels_applied=False, panel_open=False)
    labels = draw_browser_scene(mark, labels_applied=True, panel_open=False)
    open_scene = draw_browser_scene(mark, labels_applied=True, panel_open=True)
    decision_wide = draw_browser_scene(mark, labels_applied=True, panel_open=True, cursor="cta")
    decision = crop_level(decision_wide, (340, 74, 1555, 848))
    next_scene = draw_browser_scene(mark, labels_applied=True, panel_open=True, next_email=True)
    sequence = draw_review_sequence(mark)
    parity = draw_provider_parity(mark)

    assets = {
        "quiet": quiet,
        "labels": labels,
        "open": open_scene,
        "decision": decision,
        "next": next_scene,
        "sequence": sequence,
        "parity": parity,
    }
    filenames = {
        "quiet": "01-quiet-inbox.png",
        "labels": "02-background-labeling.png",
        "open": "03-open-on-demand.png",
        "decision": "04-one-decision.png",
        "next": "05-next-email-background-write.png",
        "sequence": "04-decision-to-next.png",
        "parity": "06-provider-parity.png",
    }
    for key, filename in filenames.items():
        assets[key].save(OUTPUT_DIR / filename, optimize=True)

    contact_sheet = draw_contact_sheet(mark, assets)
    contact_sheet.save(OUTPUT_DIR / "threadwise-readme-storyboard.png", optimize=True)
    print(f"Rendered {len(filenames) + 2} marketing assets to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

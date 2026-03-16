from typing import Any
from functools import partial
from prompt_toolkit.layout.containers import (
    AnyContainer,
    Container,
    HSplit,
    VSplit,
    Window,
    DynamicContainer,
)
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.formatted_text import AnyFormattedText, Template

from typing import Any
from prompt_toolkit.layout.containers import (
    AnyContainer,
    Container,
    HSplit,
    VSplit,
    Window,
    DynamicContainer,
)
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.formatted_text import AnyFormattedText, Template

class InformationFrame:
    def __init__(
        self,
        body: AnyContainer,
        title: AnyFormattedText = "",
        style: str = "",
        width: Any = None,
        height: Any = None,
        top_left: str = "◇",
        top_right: str = "╮",
        bottom_left: str = "├",
        bottom_right: str = "╯",
        horizontal_char: str = "─",
        vertical_char: str = "│",
    ) -> None:
        self.body = body
        self.title = title
        self.style = style
        self.top_left = top_left
        self.top_right = top_right
        self.bottom_left = bottom_left
        self.bottom_right = bottom_right
        self.horizontal_char = horizontal_char
        self.vertical_char = vertical_char

        # 樣式獲取
        def get_border_style():
            return f"class:frame.border {self.style}"

        def get_label_style():
            return f"class:frame.label {self.style}"

        # --- 頂部列: ◇ Title ──────╮ ---
        # 使用 Window(char=...) 會自動填滿該元件分配到的所有寬度
        top_row = VSplit([
            Window(width=1, char=lambda: self.top_left, style=get_border_style),
            Window(
                content=FormattedTextControl(lambda: Template(" {} ").format(self.title)),
                style=get_label_style,
                dont_extend_width=True # 確保標題只佔用必要的寬度
            ),
            Window(char=lambda: self.horizontal_char, style=get_border_style), # 真正的動態橫線
            Window(width=1, char=lambda: self.top_right, style=get_border_style),
        ], height=1)

        # --- 中間內容列: │ body │ ---
        middle_row = VSplit([
            Window(width=1, char=lambda: self.vertical_char, style=get_border_style),
            DynamicContainer(lambda: self.body),
            Window(width=1, char=lambda: self.vertical_char, style=get_border_style),
        ])

        # --- 底部列: ├──────────────╯ ---
        bottom_row = VSplit([
            Window(width=1, char=lambda: self.bottom_left, style=get_border_style),
            Window(char=lambda: self.horizontal_char, style=get_border_style), # 真正的動態橫線
            Window(width=1, char=lambda: self.bottom_right, style=get_border_style),
        ], height=1)

        # 封裝成最終容器
        self.container = HSplit(
            [
                top_row,
                middle_row,
                bottom_row,
            ],
            width=width,
            height=height,
            style=lambda: f"class:frame {self.style}",
        )

    def __pt_container__(self) -> Container:
        return self.container
    
if __name__ == "__main__":
    from prompt_toolkit.widgets import TextArea
    from prompt_toolkit import Application
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.key_binding import KeyBindings

    content = TextArea(text="Interactive mode is enabled.\nparams:\ninput : (required)", width=10)
    info_box = InformationFrame(
        body=content,
        title="Information",
        style="fg:cyan",
        width=40,
    )
    
    kb = KeyBindings()
    @kb.add("c-c")
    def _(event):
        event.app.exit()
        
    @kb.add("c")
    def _(event):
        info_box.style = "fg:green" if info_box.style == "fg:cyan" else "fg:cyan"
        
    app = Application(layout=Layout(info_box), full_screen=False, key_bindings=kb)
    
    app.run()
    
    
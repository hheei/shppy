from __future__ import annotations

from typing import Any, Callable
from collections import defaultdict
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import Completer, DummyCompleter
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, VSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.styles import Style
from prompt_toolkit.shortcuts import print_container
from prompt_toolkit.layout.dimension import Dimension as D
from prompt_toolkit.utils import get_cwidth
from shppy.tui.helper import GhostTextProcessor

PROMPT_STYLE_DICT = {
    "title": "ansiblue",
    "title.active": "bold ansiblue",
    "grid": "ansibrightblack",
    "grid.active": "ansibrightcyan",
    "success": "bold ansigreen",
    "value": "ansibrightblack",
    "value.active": "bold ansiblue",
    "value.error": "bold ansired",
    "mark": "ansibrightcyan",
    "tail": "ansibrightblack",
    "tail.inactive": "ansibrightblack",
    "tail.active": "ansibrightcyan",
    "input": "ansibrightblack",
    "input.active": "ansiwhite",
    "ghost": "ansibrightblack",
    "error": "bold ansired",
    "choice": "ansibrightblack",
    "choice.active": "ansiwhite",
}

class StepPromptBase:
    def __init__(self, 
                 vertical = {"": "│", "active": "│"}, 
                 top_left = {"": "◇", "active": "◆"}, 
                 low_left = {"": "│", "active": "└"},
                 style: Style | None = None
                 ):
        self.state = ""
        self.vertical = vertical
        self.top_left = top_left
        self.low_left = low_left
        if style is None:
            self.style = Style.from_dict(PROMPT_STYLE_DICT)
        else:
            self.style = style
        
    def run(self) -> Any:
        pass

    def build_left(self, h: int = 1):
        grid_style_fn = lambda: self._parse("class:grid")
        module = HSplit([
            Window(height=1,char=lambda: self.top_left[self.state], style = grid_style_fn),
            Window(height=D(min=h), char=lambda: self.vertical[self.state], style = grid_style_fn),
            Window(height=1,char=lambda: self.low_left[self.state], style = grid_style_fn),
        ],
                        width=1)
        
        return module
    
    def _parse(self, key):
        base = key[6:] if key.startswith("class:") else key
        if f"{base}.{self.state}" in PROMPT_STYLE_DICT:
            return f"class:{base}.{self.state}"
        if base in PROMPT_STYLE_DICT:
            return f"class:{base}"
        return key

class TitlePrompt(StepPromptBase):
    def __init__(self, 
                 title, 
                 top_left=defaultdict(lambda: "┌"), 
                 low_left=defaultdict(lambda: "│"),
                 style: Style | None = None
                 ):
        super().__init__(top_left=top_left, low_left=low_left, style=style)
        self.title = title

    def run(self):
        left = self.build_left(h=0)
        mid = Window(FormattedTextControl(lambda: [(self._parse("class:title.active"), self.title)]))
        module = VSplit([left,mid], padding=1)
        print_container(module, style=self.style)

class FillPrompt(StepPromptBase):
    def __init__(
        self,
        title: str,
        value: str = "",
        style: Style | None = None,
    ):
        super().__init__(style=style)
        self.title = title
        self.value = value

    def run(
        self,
        completer: Completer | DummyCompleter | None = None,
        error_message: str = "",
        ghost: str | None = None,
        validator: Callable[[str], tuple[bool, str]] | None = None,
    ) -> str:
        self.state = "active"
        left = self.build_left()
        
        input_buffer = Buffer(completer=completer or DummyCompleter(), complete_while_typing=True)
        input_buffer.text = self.value
        input_buffer.cursor_position = len(input_buffer.text)
        input_control = BufferControl(
            buffer=input_buffer,
            input_processors=[GhostTextProcessor(lambda: (ghost or "").strip() if not input_buffer.text else "")],
        )
        value_row = Window(content=input_control, height=1, style=lambda: self._parse("class:input"))
        submitted_text = ""
        cancelled = False
        current_error = error_message
        max_completion_items = 5

        def _clear_error_on_change(_) -> None:
            nonlocal current_error
            if current_error:
                current_error = ""

        input_buffer.on_text_changed += _clear_error_on_change

        title_row = Window(
            FormattedTextControl(lambda: [(self._parse("class:title"), self.title)]),
            height=1,
        )

        def _build_tail_fragments():
            if current_error:
                return [(self._parse("class:error"), f"!! {current_error}")]

            def _shorten_item(text: str) -> str:
                return text if len(text) <= 14 else f"{text[:12]}..."

            complete_state = input_buffer.complete_state
            completions = list(getattr(complete_state, "completions", []) or []) if complete_state is not None else []
            if not completions:
                return [(self._parse("class:tail.inactive"), "")]

            complete_index = getattr(complete_state, "complete_index", None)
            if complete_index is None or complete_index < 0:
                complete_index = 0

            has_pagination = len(completions) > max_completion_items
            page_start = 0
            page_end = len(completions)
            if has_pagination:
                page_start = (complete_index // max_completion_items) * max_completion_items
                page_end = min(page_start + max_completion_items, len(completions))

            visible = completions[page_start:page_end]
            fragments = []

            if has_pagination:
                total_pages = (len(completions) + max_completion_items - 1) // max_completion_items
                current_page = (complete_index // max_completion_items) + 1
                fragments.append((self._parse("class:tail.inactive"), f"[{current_page:02d}/{total_pages:02d}] < "))

            for idx, completion in enumerate(visible):
                actual_index = page_start + idx
                text = _shorten_item(completion.display_text or completion.text)
                if idx > 0:
                    fragments.append((self._parse("class:tail.inactive"), "  "))

                if complete_index == actual_index:
                    fragments.append((self._parse("class:input.active"), text))
                else:
                    fragments.append((self._parse("class:tail.inactive"), text))

            if has_pagination:
                fragments.append((self._parse("class:tail.inactive"), " >"))

            return fragments

        tail_row = Window(
            FormattedTextControl(_build_tail_fragments),
            height=1,
        )

        right = HSplit([title_row, value_row, tail_row])
        
        module = VSplit([left, right], padding=1)

        kb = KeyBindings()

        def _move_completion(delta: int) -> None:
            if delta == 0:
                return

            if input_buffer.complete_state is None:
                input_buffer.start_completion(select_first=False)
                if input_buffer.complete_state is None:
                    return

            move = input_buffer.complete_next if delta > 0 else input_buffer.complete_previous
            for _ in range(abs(delta)):
                move()

        @kb.add("c-c")
        def _(event) -> None:
            nonlocal cancelled
            cancelled = True
            input_buffer.cancel_completion()
            self.state = ""
            event.app.exit()
            raise KeyboardInterrupt("Input cancelled by user.")

        @kb.add("up")
        def _(event) -> None:
            if input_buffer.complete_state is not None:
                step = max_completion_items if len(getattr(input_buffer.complete_state, "completions", []) or []) > max_completion_items else 1
                _move_completion(-step)

        @kb.add("down")
        def _(event) -> None:
            if input_buffer.complete_state is not None:
                step = max_completion_items if len(getattr(input_buffer.complete_state, "completions", []) or []) > max_completion_items else 1
                _move_completion(step)

        @kb.add("tab")
        def _(event) -> None:
            nonlocal current_error
            current_error = ""
            if input_buffer.complete_state is None:
                input_buffer.start_completion(select_first=True)
            else:
                _move_completion(1)
            event.app.invalidate()

        @kb.add("s-tab")
        def _(event) -> None:
            nonlocal current_error
            current_error = ""
            if input_buffer.complete_state is None:
                input_buffer.start_completion(select_first=False)
            if input_buffer.complete_state is not None:
                _move_completion(-1)
            event.app.invalidate()

        @kb.add("left")
        def _(event) -> None:
            if input_buffer.complete_state is not None:
                _move_completion(-1)
            else:
                event.current_buffer.cursor_left(count=1)

        @kb.add("right")
        def _(event) -> None:
            if input_buffer.complete_state is not None:
                _move_completion(1)
            else:
                event.current_buffer.cursor_right(count=1)

        @kb.add("enter")
        def _(event) -> None:
            nonlocal submitted_text, current_error

            complete_state = input_buffer.complete_state
            if complete_state is not None and complete_state.current_completion is not None:
                input_buffer.apply_completion(complete_state.current_completion)

            candidate = input_buffer.text.strip()
            input_buffer.text = candidate
            input_buffer.text
            if validator is not None:
                ok, message = validator(candidate)
                if not ok:
                    current_error = message
                    event.app.invalidate()
                    return
            submitted_text = candidate
            current_error = ""
            input_buffer.cancel_completion()
            self.state = ""
            event.app.invalidate()
            event.app.exit()

        app = Application(
            layout=Layout(
                module,
                focused_element=value_row,
            ),
            key_bindings=kb,
            full_screen=False,
            style=self.style,
        )
        app.run()
        input_buffer.cancel_completion()
        
        return submitted_text


class MultiSelectPrompt(StepPromptBase):
    def __init__(self, title: str, options: list[str], selected: list[str] | None = None, style: Style | None = None):
        super().__init__(style=style)
        self.title = title
        self.options = options
        self.selected = selected or []

    def run(
        self,
        error_message: str = "",
        page_size: int = 6,
        validator: Callable[[list[str]], tuple[bool, str]] | None = None,
        min_selected: int | None = None,
        max_selected: int | None = None,
    ) -> list[str]:
        self.state = "active"
        left = self.build_left()
        submitted_values = []
        submitted = False
        current_error = error_message
        page_size = max(1, page_size)
        if min_selected is not None:
            min_selected = max(0, min_selected)
        if max_selected is not None:
            max_selected = max(0, max_selected)
        if min_selected is not None and max_selected is not None and min_selected > max_selected:
            raise ValueError("min_selected cannot be greater than max_selected.")
        cursor_index = 0
        selected_set = {item for item in self.selected if item in self.options}
        if max_selected == 1 and len(selected_set) > 1:
            for item in self.options:
                if item in selected_set:
                    selected_set = {item}
                    break

        title_row = Window(FormattedTextControl(lambda: [(self._parse("class:title"), self.title)]), height=1)

        def _page_bounds() -> tuple[int, int]:
            page_start = (cursor_index // page_size) * page_size
            page_end = min(page_start + page_size, len(self.options))
            return page_start, page_end

        def _build_value_fragments():
            if not self.options:
                return [(self._parse("class:tail"), "(empty)")]

            page_start, page_end = _page_bounds()
            fragments = []
            for idx in range(page_start, page_end):
                value = self.options[idx]
                style = "class:choice.active" if idx == cursor_index else "class:choice"
                marker = "■" if value in selected_set else "□"
                fragments.append((style, f"  {marker} {value}"))
                if idx < page_end - 1:
                    fragments.append(("", "\n"))
            return fragments

        def _build_tail_fragments():
            if current_error:
                return [(self._parse("class:error"), f"!! {current_error}")]

            if not self.options:
                return [(self._parse("class:tail"), "SPACE toggle  ENTER submit")]

            page_start, page_end = _page_bounds()
            total_pages = (len(self.options) + page_size - 1) // page_size
            page_fragments = []
            if total_pages > 1:
                if page_start > 0:
                    page_fragments.append((self._parse("class:tail"), "<  "))
                page_fragments.append((self._parse("class:tail"), f"Page {(cursor_index // page_size) + 1}/{total_pages}"))
                if page_end < len(self.options):
                    page_fragments.append((self._parse("class:tail"), "  >"))
                page_fragments.append((self._parse("class:tail"), "  ·  "))
                page_fragments.append((self._parse("class:tail"), "UP/DOWN move  LEFT/RIGHT page  SPACE toggle  ENTER submit"))
            else:
                page_fragments.append((self._parse("class:tail"), "UP/DOWN move  SPACE toggle  ENTER submit"))
            return page_fragments

        value_row = Window(
            FormattedTextControl(
                _build_value_fragments
            ),
            height=D(min=1, max=page_size),
            always_hide_cursor=True,
        )

        tail_row = Window(
            FormattedTextControl(
                _build_tail_fragments
            ),
            height=1,
        )

        right = HSplit([title_row, value_row, tail_row])
        module = VSplit([left, right], padding=1)

        kb = KeyBindings()

        def _move_cursor(delta: int) -> None:
            nonlocal cursor_index
            if not self.options or delta == 0:
                return
            cursor_index = min(max(0, cursor_index + delta), len(self.options) - 1)

        @kb.add("c-c")
        def _(event) -> None:
            self.state = ""
            event.app.exit()
            raise KeyboardInterrupt("Input cancelled by user.")

        @kb.add("up")
        def _(event) -> None:
            _move_cursor(-1)
            event.app.invalidate()

        @kb.add("down")
        def _(event) -> None:
            _move_cursor(1)
            event.app.invalidate()

        @kb.add("left")
        def _(event) -> None:
            _move_cursor(-page_size)
            event.app.invalidate()

        @kb.add("right")
        def _(event) -> None:
            _move_cursor(page_size)
            event.app.invalidate()

        @kb.add("space")
        def _(event) -> None:
            nonlocal current_error
            current_error = ""
            if not self.options:
                event.app.invalidate()
                return
            value = self.options[cursor_index]
            if value in selected_set:
                selected_set.remove(value)
            else:
                if max_selected == 1:
                    selected_set.clear()
                selected_set.add(value)
            event.app.invalidate()

        @kb.add("enter")
        def _(event) -> None:
            nonlocal submitted_values, current_error, submitted
            candidate = [item for item in self.options if item in selected_set]
            if min_selected is not None and len(candidate) < min_selected:
                current_error = f"Select at least {min_selected} item(s)."
                event.app.invalidate()
                return
            if max_selected is not None and len(candidate) > max_selected:
                current_error = f"Select at most {max_selected} item(s)."
                event.app.invalidate()
                return
            if validator is not None:
                ok, message = validator(candidate)
                if not ok:
                    current_error = message
                    event.app.invalidate()
                    return
            submitted_values = candidate
            submitted = True
            current_error = ""
            self.state = ""
            event.app.invalidate()
            event.app.exit()

        app = Application(
            layout=Layout(
                module,
                focused_element=value_row,
            ),
            key_bindings=kb,
            full_screen=False,
            erase_when_done=True,
            style=self.style,
        )
        app.run()

        if submitted:
            rows = [
                VSplit([
                    Window(FormattedTextControl(lambda: [(self._parse("class:grid"), "◇")]), width=1, height=1, dont_extend_width=True),
                    Window(width=1),
                    Window(FormattedTextControl(lambda: [(self._parse("class:title"), self.title)]), height=1),
                ])
            ]
            for value in self.options:
                marker = "■" if value in selected_set else "□"
                rows.append(
                    VSplit([
                        Window(FormattedTextControl(lambda: [(self._parse("class:grid"), "│")]), width=1, height=1, dont_extend_width=True),
                        Window(width=1),
                        Window(FormattedTextControl(lambda v=value, m=marker: [("class:choice", f"  {m} {v}")]), height=1),
                    ])
                )
            rows.append(
                VSplit([
                    Window(FormattedTextControl(lambda: [(self._parse("class:grid"), "│")]), width=1, height=1, dont_extend_width=True),
                    Window(width=1),
                    Window(FormattedTextControl(lambda: [("", "")]), height=1),
                ])
            )
            print_container(HSplit(rows), style=self.style)

        return submitted_values


class InfoPrompt(StepPromptBase):
    def __init__(
        self,
        title: str,
        line: str,
        padding_right: int = 4,
        style: Style | None = None,
    ):
        low_left = defaultdict(lambda: "│")
        super().__init__(low_left=low_left, style=style)
        self.title = title
        self.line = line
        self.padding_right = max(0, padding_right)

    def run(self) -> None:
        inner_width = max(
            1,
            get_cwidth(self.title),
            *(get_cwidth(line) + 2 for line in self.line.split("\n")),
        )
        title_tail = max(1, inner_width + self.padding_right - get_cwidth(self.title))

        grid_sty = lambda: self._parse("class:grid")
        top = VSplit([
            Window(height=1, width=1, char=lambda: self.top_left[self.state], style=grid_sty),
            Window(width=1), # padding
            Window(FormattedTextControl(lambda: [(self._parse("class:title"), self.title)]), dont_extend_width=True),
            Window(width=1), # padding
            Window(width=title_tail, char="─", style=grid_sty),
            Window(height=1, width=1, char="╮", style=grid_sty),
        ], height=1)
        mid = VSplit([
            Window(width=1, char="│", style=grid_sty),
            Window(width=1), # padding
            TextArea(text=self.line, read_only=True, width=inner_width, style=self._parse("class:value")),
            Window(width=1), # padding
            Window(width=self.padding_right),
            Window(width=1, char="│", style=grid_sty),
        ], padding = 0)
        bottom = VSplit([
            Window(width=1, height=1, char="├", style=grid_sty),
            Window(width=inner_width + 2 + self.padding_right, char="─", style=grid_sty),
            Window(width=1, height=1, char="╯", style=grid_sty),
        ], height=1)
        bot_add = Window(width=1, height=1, char=lambda: self.low_left[self.state], style=grid_sty, dont_extend_width=True)
        
        module = HSplit([top, mid, bottom, bot_add])
        print_container(module, style=self.style)


class FinishPrompt(StepPromptBase):
    def __init__(
        self,
        success: bool,
        message: str | None = None,
        style: Style | None = None,
    ):
        super().__init__(style=style)
        self.state = "active"
        self.success = success
        self.message = message or ("Success!" if success else "Error!")

    def run(self) -> None:
        status_style = "class:success" if self.success else "class:error"
        left = Window(
            FormattedTextControl(lambda: [(self._parse("class:grid"), "◆")]),
            width=1,
            height=1,
        )
        right = Window(
            FormattedTextControl(lambda: [(status_style, self.message)]),
            height=1,
        )
        module = VSplit([left, right], padding=1)
        print_container(module, style=self.style)
        
        
if __name__ == "__main__":
    prompt = MultiSelectPrompt("Select options", ["Option 1", "Option 2", "Option 3"], selected=["Option 2"])
    result = prompt.run(min_selected=1)
    FinishPrompt(True).run()
    print("Selected:", result)

"""Ensure that Event Chains are properly queued and handled between frontend and backend."""

import time
from typing import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness

MANY_EVENTS = 50


def EventChain():
    """App with chained event handlers."""
    import reflex as rx

    # repeated here since the outer global isn't exported into the App module
    MANY_EVENTS = 50

    class State(rx.State):
        event_order: list[str] = []

        @rx.var
        def token(self) -> str:
            return self.get_token()

        def event_no_args(self):
            self.event_order.append("event_no_args")

        def event_arg(self, arg):
            self.event_order.append(f"event_arg:{arg}")

        def event_nested_1(self):
            self.event_order.append("event_nested_1")
            yield State.event_nested_2
            yield State.event_arg("nested_1")  # type: ignore

        def event_nested_2(self):
            self.event_order.append("event_nested_2")
            yield State.event_nested_3
            yield rx.console_log("event_nested_2")
            yield State.event_arg("nested_2")  # type: ignore

        def event_nested_3(self):
            self.event_order.append("event_nested_3")
            yield State.event_no_args
            yield State.event_arg("nested_3")  # type: ignore

        def on_load_return_chain(self):
            self.event_order.append("on_load_return_chain")
            return [State.event_arg(1), State.event_arg(2), State.event_arg(3)]  # type: ignore

        def on_load_yield_chain(self):
            self.event_order.append("on_load_yield_chain")
            yield State.event_arg(4)  # type: ignore
            yield State.event_arg(5)  # type: ignore
            yield State.event_arg(6)  # type: ignore

        def click_return_event(self):
            self.event_order.append("click_return_event")
            return State.event_no_args

        def click_return_events(self):
            self.event_order.append("click_return_events")
            return [
                State.event_arg(7),  # type: ignore
                rx.console_log("click_return_events"),
                State.event_arg(8),  # type: ignore
                State.event_arg(9),  # type: ignore
            ]

        def click_yield_chain(self):
            self.event_order.append("click_yield_chain:0")
            yield State.event_arg(10)  # type: ignore
            self.event_order.append("click_yield_chain:1")
            yield rx.console_log("click_yield_chain")
            yield State.event_arg(11)  # type: ignore
            self.event_order.append("click_yield_chain:2")
            yield State.event_arg(12)  # type: ignore
            self.event_order.append("click_yield_chain:3")

        def click_yield_many_events(self):
            self.event_order.append("click_yield_many_events")
            for ix in range(MANY_EVENTS):
                yield State.event_arg(ix)  # type: ignore
                yield rx.console_log(f"many_events_{ix}")
            self.event_order.append("click_yield_many_events_done")

        def click_yield_nested(self):
            self.event_order.append("click_yield_nested")
            yield State.event_nested_1
            yield State.event_arg("yield_nested")  # type: ignore

        def redirect_return_chain(self):
            self.event_order.append("redirect_return_chain")
            yield rx.redirect("/on-load-return-chain")

        def redirect_yield_chain(self):
            self.event_order.append("redirect_yield_chain")
            yield rx.redirect("/on-load-yield-chain")

    app = rx.App(state=State)

    @app.add_page
    def index():
        return rx.fragment(
            rx.input(value=State.token, readonly=True, id="token"),
            rx.button(
                "Return Event",
                id="return_event",
                on_click=State.click_return_event,
            ),
            rx.button(
                "Return Events",
                id="return_events",
                on_click=State.click_return_events,
            ),
            rx.button(
                "Yield Chain",
                id="yield_chain",
                on_click=State.click_yield_chain,
            ),
            rx.button(
                "Yield Many events",
                id="yield_many_events",
                on_click=State.click_yield_many_events,
            ),
            rx.button(
                "Yield Nested",
                id="yield_nested",
                on_click=State.click_yield_nested,
            ),
            rx.button(
                "Redirect Yield Chain",
                id="redirect_yield_chain",
                on_click=State.redirect_yield_chain,
            ),
            rx.button(
                "Redirect Return Chain",
                id="redirect_return_chain",
                on_click=State.redirect_return_chain,
            ),
        )

    def on_load_return_chain():
        return rx.fragment(
            rx.text("return"),
            rx.input(value=State.token, readonly=True, id="token"),
        )

    def on_load_yield_chain():
        return rx.fragment(
            rx.text("yield"),
            rx.input(value=State.token, readonly=True, id="token"),
        )

    def on_mount_return_chain():
        return rx.fragment(
            rx.text(
                "return",
                on_mount=State.on_load_return_chain,
                on_unmount=lambda: State.event_arg("unmount"),  # type: ignore
            ),
            rx.input(value=State.token, readonly=True, id="token"),
            rx.button("Unmount", on_click=rx.redirect("/"), id="unmount"),
        )

    def on_mount_yield_chain():
        return rx.fragment(
            rx.text(
                "yield",
                on_mount=[
                    State.on_load_yield_chain,
                    lambda: State.event_arg("mount"),  # type: ignore
                ],
                on_unmount=State.event_no_args,
            ),
            rx.input(value=State.token, readonly=True, id="token"),
            rx.button("Unmount", on_click=rx.redirect("/"), id="unmount"),
        )

    app.add_page(on_load_return_chain, on_load=State.on_load_return_chain)  # type: ignore
    app.add_page(on_load_yield_chain, on_load=State.on_load_yield_chain)  # type: ignore
    app.add_page(on_mount_return_chain)
    app.add_page(on_mount_yield_chain)

    app.compile()


@pytest.fixture(scope="session")
def event_chain(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start EventChain app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("event_chain"),
        app_source=EventChain,  # type: ignore
    ) as harness:
        yield harness


@pytest.fixture
def driver(event_chain: AppHarness):
    """Get an instance of the browser open to the event_chain app.

    Args:
        event_chain: harness for EventChain app

    Yields:
        WebDriver instance.
    """
    assert event_chain.app_instance is not None, "app is not running"
    driver = event_chain.frontend()
    try:
        assert event_chain.poll_for_clients()
        yield driver
    finally:
        driver.quit()


@pytest.mark.parametrize(
    ("button_id", "exp_event_order"),
    [
        ("return_event", ["click_return_event", "event_no_args"]),
        (
            "return_events",
            ["click_return_events", "event_arg:7", "event_arg:8", "event_arg:9"],
        ),
        (
            "yield_chain",
            [
                "click_yield_chain:0",
                "click_yield_chain:1",
                "click_yield_chain:2",
                "click_yield_chain:3",
                "event_arg:10",
                "event_arg:11",
                "event_arg:12",
            ],
        ),
        (
            "yield_many_events",
            [
                "click_yield_many_events",
                "click_yield_many_events_done",
                *[f"event_arg:{ix}" for ix in range(MANY_EVENTS)],
            ],
        ),
        (
            "yield_nested",
            [
                "click_yield_nested",
                "event_nested_1",
                "event_arg:yield_nested",
                "event_nested_2",
                "event_arg:nested_1",
                "event_nested_3",
                "event_arg:nested_2",
                "event_no_args",
                "event_arg:nested_3",
            ],
        ),
        (
            "redirect_return_chain",
            [
                "redirect_return_chain",
                "on_load_return_chain",
                "event_arg:1",
                "event_arg:2",
                "event_arg:3",
            ],
        ),
        (
            "redirect_yield_chain",
            [
                "redirect_yield_chain",
                "on_load_yield_chain",
                "event_arg:4",
                "event_arg:5",
                "event_arg:6",
            ],
        ),
    ],
)
def test_event_chain_click(event_chain, driver, button_id, exp_event_order):
    """Click the button, assert that the events are handled in the correct order.

    Args:
        event_chain: AppHarness for the event_chain app
        driver: selenium WebDriver open to the app
        button_id: the ID of the button to click
        exp_event_order: the expected events recorded in the State
    """
    token_input = driver.find_element(By.ID, "token")
    btn = driver.find_element(By.ID, button_id)
    assert token_input
    assert btn

    token = event_chain.poll_for_value(token_input)

    btn.click()
    if "redirect" in button_id:
        # wait a bit longer if we're redirecting
        time.sleep(1)
    if "many_events" in button_id:
        # wait a bit longer if we have loads of events
        time.sleep(1)
    time.sleep(0.5)
    backend_state = event_chain.app_instance.state_manager.states[token]
    assert backend_state.event_order == exp_event_order


@pytest.mark.parametrize(
    ("uri", "exp_event_order"),
    [
        (
            "/on-load-return-chain",
            [
                "on_load_return_chain",
                "event_arg:1",
                "event_arg:2",
                "event_arg:3",
            ],
        ),
        (
            "/on-load-yield-chain",
            [
                "on_load_yield_chain",
                "event_arg:4",
                "event_arg:5",
                "event_arg:6",
            ],
        ),
    ],
)
def test_event_chain_on_load(event_chain, driver, uri, exp_event_order):
    """Load the URI, assert that the events are handled in the correct order.

    Args:
        event_chain: AppHarness for the event_chain app
        driver: selenium WebDriver open to the app
        uri: the page to load
        exp_event_order: the expected events recorded in the State
    """
    driver.get(event_chain.frontend_url + uri)
    token_input = driver.find_element(By.ID, "token")
    assert token_input

    token = event_chain.poll_for_value(token_input)

    time.sleep(0.5)
    backend_state = event_chain.app_instance.state_manager.states[token]
    assert backend_state.event_order == exp_event_order


@pytest.mark.parametrize(
    ("uri", "exp_event_order"),
    [
        (
            "/on-mount-return-chain",
            [
                "on_load_return_chain",
                "event_arg:unmount",
                "on_load_return_chain",
                "event_arg:1",
                "event_arg:2",
                "event_arg:3",
                "event_arg:1",
                "event_arg:2",
                "event_arg:3",
                "event_arg:unmount",
            ],
        ),
        (
            "/on-mount-yield-chain",
            [
                "on_load_yield_chain",
                "event_arg:mount",
                "event_no_args",
                "on_load_yield_chain",
                "event_arg:mount",
                "event_arg:4",
                "event_arg:5",
                "event_arg:6",
                "event_arg:4",
                "event_arg:5",
                "event_arg:6",
                "event_no_args",
            ],
        ),
    ],
)
def test_event_chain_on_mount(event_chain, driver, uri, exp_event_order):
    """Load the URI, assert that the events are handled in the correct order.

    These pages use `on_mount` and `on_unmount`, which get fired twice in dev mode
    due to react StrictMode being used.

    In prod mode, these events are only fired once.

    Args:
        event_chain: AppHarness for the event_chain app
        driver: selenium WebDriver open to the app
        uri: the page to load
        exp_event_order: the expected events recorded in the State
    """
    driver.get(event_chain.frontend_url + uri)
    token_input = driver.find_element(By.ID, "token")
    assert token_input

    token = event_chain.poll_for_value(token_input)

    unmount_button = driver.find_element(By.ID, "unmount")
    assert unmount_button
    unmount_button.click()

    time.sleep(1)
    backend_state = event_chain.app_instance.state_manager.states[token]
    assert backend_state.event_order == exp_event_order
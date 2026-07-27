"""Compatibility imports for the legacy ``src/main.py`` application module."""

from fish_demo.app import (
    RuntimeResources,
    _handle_sprite_import,
    _main,
    _try_transfer,
    main,
    startup_options,
)
from fish_demo.input_handlers import (
    _enter_fullscreen,
    _exit_fullscreen,
    _toggle_fullscreen,
    handle_key,
    spawn_fish,
)
from fish_demo.network_handlers import (
    _request_missing_sprites,
    handle_network_message,
    send_sprite_data_async,
)

_send_sprite_data_async = send_sprite_data_async

__all__ = [
    "RuntimeResources",
    "_enter_fullscreen",
    "_exit_fullscreen",
    "_handle_sprite_import",
    "_main",
    "_request_missing_sprites",
    "_send_sprite_data_async",
    "_toggle_fullscreen",
    "_try_transfer",
    "handle_key",
    "handle_network_message",
    "main",
    "send_sprite_data_async",
    "spawn_fish",
    "startup_options",
]


if __name__ == "__main__":
    raise SystemExit(main())

permit(
    principal,
    action == Action::"send_message",
    resource == MessageType::"inventory.monitor.observe"
)
when {
    principal.scopes.contains(
        "inventory_a2a:manage"
    )
};

permit(
    principal,
    action == Action::"send_message",
    resource == MessageType::"inventory.monitor"
)
when {
    principal.scopes.contains(
        "inventory_a2a:monitor"
    )
};
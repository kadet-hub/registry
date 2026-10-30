"""Container images of a recipe's rendered Kubernetes objects (REC-12). Standard library only."""

POD_LISTS = ("containers", "initContainers", "ephemeralContainers")


def images(docs):
    """The image of every item of a containers, initContainers or ephemeralContainers list at any depth, once each, sorted."""
    found, todo = set(), list(docs)
    while todo:
        node = todo.pop()
        if isinstance(node, dict):
            for key, value in node.items():
                if key in POD_LISTS and isinstance(value, list):
                    found.update(c["image"] for c in value if isinstance(c, dict) and isinstance(c.get("image"), str))
                todo.append(value)
        elif isinstance(node, list):
            todo.extend(node)
    return sorted(found)

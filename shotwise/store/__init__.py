def make_store(config):
    limits = {name: p.limits for name, p in config.providers.items()}
    path = config.root / config.pipeline.storage.path
    if config.pipeline.storage.backend == "json":
        from shotwise.store.jsonfile import JsonStore
        return JsonStore(path, limits)
    from shotwise.store.sqlite import SqliteStore
    return SqliteStore(path, limits)

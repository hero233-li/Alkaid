def test_celery_autodiscovery_registers_product_application_task() -> None:
    from config.celery import app

    original_eager = app.conf.task_always_eager
    try:
        app.conf.task_always_eager = False
        app.loader.import_default_modules()
        assert "apps.product_data.tasks.execute_product_application" in app.tasks
    finally:
        app.conf.task_always_eager = original_eager


def test_product_application_compatibility_task_remains_importable() -> None:
    import apps.product_data.tasks as product_data_tasks

    assert (
        product_data_tasks.execute_product_application.name
        == "apps.product_data.tasks.execute_product_application"
    )

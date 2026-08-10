def test_celery_autodiscovery_registers_product_application_task() -> None:
    from config.celery import app

    original_eager = app.conf.task_always_eager
    try:
        app.conf.task_always_eager = False
        app.loader.import_default_modules()
        assert "apps.workflow.product_applications.tasks.execute_product_application" in app.tasks
    finally:
        app.conf.task_always_eager = original_eager


def test_product_application_task_keeps_external_celery_name() -> None:
    import apps.workflow.product_applications.tasks as product_application_tasks

    assert (
        product_application_tasks.execute_product_application.name
        == "apps.workflow.product_applications.tasks.execute_product_application"
    )

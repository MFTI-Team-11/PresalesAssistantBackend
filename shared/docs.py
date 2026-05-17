from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html


def install_docs(app: FastAPI, title: str) -> None:
    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url="./openapi.json",
            title=f"{title} - Swagger UI",
        )

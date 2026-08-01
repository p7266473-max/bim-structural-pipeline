import reflex as rx

config = rx.Config(
    app_name="T",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)
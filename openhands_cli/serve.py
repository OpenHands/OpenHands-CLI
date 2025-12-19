from textual_serve.server import Server


server = Server("uv run openhands --exp")
server.serve(debug=True)

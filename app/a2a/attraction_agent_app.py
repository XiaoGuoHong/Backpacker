from app.a2a.agent import create_attraction_agent
from app.a2a.server import create_a2a_app
from app.core.config import get_settings

settings = get_settings()
agent = create_attraction_agent(settings)
app = create_a2a_app(agent, settings)

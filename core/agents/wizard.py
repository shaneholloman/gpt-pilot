import json
import secrets
from json import JSONDecodeError
from urllib.parse import urljoin
from uuid import uuid4

import httpx
import yaml

from core.agents.base import BaseAgent
from core.agents.response import AgentResponse
from core.config import SWAGGER_EMBEDDINGS_API
from core.log import get_logger
from core.templates.registry import PROJECT_TEMPLATES
from core.ui.base import ProjectStage

log = get_logger(__name__)


class Wizard(BaseAgent):
    agent_type = "wizard"
    display_name = "Wizard"

    def load_docs(self, docs: str) -> dict[str, any]:
        try:
            return json.loads(docs)
        except JSONDecodeError:
            try:
                return yaml.safe_load(docs)
            except Exception as e:
                log.error(f"An error occurred: {str(e)}")
                return {}

    def get_auth_methods(self, docs: dict[str, any]) -> dict[str, any]:
        auth_methods = {}
        if "components" in docs and "securitySchemes" in docs["components"]:
            auth_methods["types"] = [details["type"] for details in docs["components"]["securitySchemes"].values()]
            auth_methods["api_version"] = 3
            auth_methods["external_api_url"] = docs.get("servers", [{}])[0].get("url", "")

        elif "securityDefinitions" in docs:
            auth_methods["types"] = [details["type"] for details in docs["securityDefinitions"].values()]
            auth_methods["api_version"] = 2
            auth_methods["external_api_url"] = (
                "https://" + docs.get("host", "api.example.com") + docs.get("basePath", "")
            )
        return auth_methods

    def create_custom_buttons(self, auth_methods):
        custom_values = {
            "basic": "HTTP Basic",
            "bearer": "HTTP Bearer",
            "apiKey": "API Key",
            "openIdConnect": "OpenID Connect",
            "oauth2": "OAuth2",
        }
        return {method: custom_values[method] for method in auth_methods if method in custom_values}

    async def run(self) -> AgentResponse:
        await self.init_frontend()
        return AgentResponse.done(self)

    async def init_frontend(self):
        """
        Sets up the frontend

        :return: AgentResponse.done(self)
        """
        auth_methods = {}
        options = {}

        await self.ui.send_project_stage({"stage": ProjectStage.PROJECT_DESCRIPTION})

        description = await self.ask_question(
            "Please describe the app you want to build.",
            allow_empty=False,
            full_screen=True,
        )
        description = description.text.strip()

        if self.state_manager.project.project_type == "swagger":
            while True:
                try:
                    docs = await self.ask_question(
                        "Paste the OpenAPI/Swagger JSON or YAML docs here",
                        allow_empty=False,
                        verbose=True,
                    )
                    content = self.load_docs(docs.text.strip())
                    auth_methods = self.get_auth_methods(content)

                    self.next_state.knowledge_base["docs"] = content

                    self.next_state.knowledge_base["docs"]["api_version"] = auth_methods["api_version"]

                    self.next_state.knowledge_base["docs"]["external_api_url"] = auth_methods["external_api_url"]

                    try:
                        url = urljoin(SWAGGER_EMBEDDINGS_API, "upload")
                        async with httpx.AsyncClient(
                            transport=httpx.AsyncHTTPTransport(retries=3), timeout=httpx.Timeout(30.0, connect=60.0)
                        ) as client:
                            await client.post(
                                url,
                                json={
                                    "text": docs.text.strip(),
                                    "project_id": str(self.state_manager.project.id),
                                    "user_id": "1",
                                },
                            )

                    except Exception as e:
                        log.warning(f"Failed to fetch from RAG service: {e}", exc_info=True)

                    break
                except Exception as e:
                    log.debug(f"An error occurred: {str(e)}")
                    await self.send_message("Please provide a valid input.")
                    continue

            if len(auth_methods) > 1:
                question = "Pythagora detected multiple authentication methods in your API docs. Do you need authentication in your app (login, register, etc.)?"
            elif len(auth_methods) == 1:
                question = f'Pythagora detected {next(iter(self.create_custom_buttons(auth_methods["types"])))} authentication in your API docs. Do you want to use it?'
            else:
                question = "Pythagora didn't detect any authentication methods in your API docs. Do you need authentication in your app (login, register, etc.)?"

            auth_needed = await self.ask_question(
                question,
                buttons={
                    "yes": "Yes",
                    "no": "No",
                },
                buttons_only=True,
                default="no",
            )

            if auth_needed.button == "yes":
                options["auth"] = True

                auth_type_question = await self.ask_question(
                    "Which authentication method do you want to use?",
                    buttons=self.create_custom_buttons(auth_methods["types"]),
                    buttons_only=True,
                    default=next(iter(self.create_custom_buttons(auth_methods["types"]))),
                )

                if auth_type_question.button == "apiKey":
                    api_key = await self.ask_question(
                        "Enter your API key here",
                        allow_empty=False,
                        verbose=True,
                    )
                    options["auth_type"] = "api_key"
                    options["api_key"] = api_key.text.strip()
                    options["external_api_url"] = self.next_state.knowledge_base["docs"]["external_api_url"]
                elif auth_type_question.button == "basic":
                    raise NotImplementedError()
                elif auth_type_question.button == "bearer":
                    raise NotImplementedError()
                elif auth_type_question.button == "openIdConnect":
                    raise NotImplementedError()
                elif auth_type_question.button == "oauth2":
                    raise NotImplementedError()

        else:
            auth_needed = await self.ask_question(
                "Do you need authentication in your app (login, register, etc.)?",
                buttons={
                    "yes": "Yes",
                    "no": "No",
                },
                buttons_only=True,
                default="no",
            )
            options = {
                "auth": auth_needed.button == "yes",
                "auth_type": "login",
                "jwt_secret": secrets.token_hex(32),
                "refresh_token_secret": secrets.token_hex(32),
            }

        self.next_state.knowledge_base["user_options"] = options
        self.state_manager.user_options = options

        await self.send_message("Setting up the project...")

        self.next_state.epics = [
            {
                "id": uuid4().hex,
                "name": "Build frontend",
                "source": "frontend",
                "description": description,
                "messages": [],
                "summary": None,
                "completed": False,
            }
        ]

        await self.apply_template(options)

        return

    async def apply_template(self, options: dict = {}):
        """
        Applies a template to the frontend.
        """
        if options["auth_type"] == "login" or options["auth_type"] == "api_key":
            template_name = "vite_react"
        else:
            raise NotImplementedError()
        template_class = PROJECT_TEMPLATES.get(template_name)
        if not template_class:
            log.error(f"Project template not found: {template_name}")
            return

        template = template_class(
            options,
            self.state_manager,
            self.process_manager,
        )

        log.info(f"Applying project template: {template.name}")
        summary = await template.apply()

        self.next_state.relevant_files = template.relevant_files
        self.next_state.modified_files = {}
        self.next_state.specification.template_summary = summary

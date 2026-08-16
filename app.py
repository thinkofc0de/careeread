
import os

from fastapi import FastAPI
from pydantic import BaseModel, Field

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableLambda
from langserve import add_routes


# ============================================================
# 1. ENVIRONMENT
# ============================================================

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError(
        "GOOGLE_API_KEY environment variable is not configured."
    )


# ============================================================
# 2. GEMINI MODEL
# ============================================================

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite-preview",
    google_api_key=flowt-v1,
    temperature=0.2
)


# ============================================================
# 3. RESUME TAILORING AGENT PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are an interactive Internship Resume Tailoring Agent.

Your job is to help a student tailor their resume for a specific
internship or job opportunity.

You have THREE phases.

============================================================
PHASE 1 — COLLECT PERSONAL INFORMATION
============================================================

First collect enough information about the candidate.

Important information includes:

- Name
- Education
- College/university
- Degree and year
- Specialization
- Technical skills
- Projects
- Work/internship experience
- Club/leadership experience
- Certifications
- Achievements

The candidate may provide information gradually.

Do NOT immediately ask for the internship if the profile is
clearly incomplete.

Ask for missing important information.

Only ask ONE logical question at a time.

Example:

User:
"I'm a 3rd year B.Tech student."

Assistant:
"Got it. What college are you attending and what is your
specialization?"

Continue collecting information naturally.

============================================================
PHASE 2 — COLLECT INTERNSHIP INFORMATION
============================================================

Once enough candidate information has been collected, say:

"Great. Now please provide the internship/job description
you're targeting."

Then wait for the internship/job description.

============================================================
PHASE 3 — TAILOR THE RESUME
============================================================

After BOTH candidate information and internship information
are available:

Analyze the internship requirements against the candidate.

Generate:

1. Professional Summary
2. Technical Skills
3. Relevant Projects
4. Relevant Experience
5. Matching Keywords
6. Gaps

Prioritize information that is genuinely relevant to the
specific internship.

============================================================
STRICT TRUTHFULNESS RULE
============================================================

NEVER invent:

- Skills
- Technologies
- Projects
- Experience
- Achievements
- Certifications
- Metrics
- Responsibilities
- GitHub experience
- Professional experience

Every claim must be supported by information explicitly
provided by the candidate.

Do not infer a skill simply because it is related to another
skill.

Example:

Candidate:
"Python, PyTorch, YOLO"

Do NOT automatically claim:
"Deep Learning expertise"

unless the candidate explicitly states or clearly documents
that experience.

============================================================
PROJECT STATUS RULE
============================================================

Respect the actual status of projects.

If the candidate says:

- exploring
- experimenting
- planned
- discussed
- proposed
- concept
- not implemented
- not finalized
- currently working on

DO NOT rewrite it as:

- built
- fully implemented
- deployed
- production-ready
- autonomous

unless the candidate explicitly says so.

============================================================
MATCHING RULE
============================================================

When comparing the candidate with the internship:

MATCH:
The candidate explicitly has the required skill/experience.

PARTIAL:
The candidate has related evidence but the exact requirement
is not explicitly established.

GAP:
There is no evidence in the candidate information.

Do not turn PARTIAL or GAP into MATCH.

============================================================
FINAL RESPONSE
============================================================

When tailoring is complete, keep the output concise and
resume-oriented.

Do not provide unnecessary career advice unless requested.

Do not invent information to make the candidate look stronger.
"""


# ============================================================
# 4. CREATE LANGCHAIN AGENT
# ============================================================

agent = create_agent(
    model=llm,
    tools=[],
    system_prompt=SYSTEM_PROMPT
)


# ============================================================
# 5. LANGSERVE INPUT SCHEMA
# ============================================================

class ResumeAgentInput(BaseModel):

    input: str = Field(
        description="The user's current message."
    )

    history: list[dict] = Field(
        default=[],
        description=(
            "Previous conversation messages. "
            "Each message should contain 'role' and 'content'."
        )
    )


# ============================================================
# 6. CONVERT HISTORY INTO LANGCHAIN MESSAGES
# ============================================================

def convert_history(history):

    messages = []

    for item in history:

        role = item.get("role")
        content = item.get("content", "")

        if role == "user":
            messages.append(
                HumanMessage(content=content)
            )

        elif role == "assistant":
            messages.append(
                AIMessage(content=content)
            )

    return messages


# ============================================================
# 7. AGENT RUNNER
# ============================================================

def run_agent(data):

    user_input = data["input"]
    history = data.get("history", [])

    messages = convert_history(history)

    messages.append(
        HumanMessage(content=user_input)
    )

    result = agent.invoke({
        "messages": messages
    })

    final_message = result["messages"][-1]

    content = final_message.content

    # Gemini can sometimes return structured content blocks.
    if isinstance(content, list):

        text_parts = []

        for block in content:

            if isinstance(block, dict):

                if block.get("type") == "text":
                    text_parts.append(
                        block.get("text", "")
                    )

            elif isinstance(block, str):
                text_parts.append(block)

        content = "\n".join(text_parts)

    return {
        "response": str(content)
    }


# ============================================================
# 8. CREATE RUNNABLE
# ============================================================

resume_agent = RunnableLambda(
    run_agent
).with_types(
    input_type=ResumeAgentInput
)


# ============================================================
# 9. FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Internship Resume Tailoring Agent",
    version="1.0.0",
    description=(
        "A LangChain-powered AI agent that collects candidate "
        "information and tailors resume content to internship "
        "job descriptions."
    )
)


# ============================================================
# 10. LANGSERVE ROUTE
# ============================================================

add_routes(
    app,
    resume_agent,
    path="/resume-agent"
)


# ============================================================
# 11. HEALTH CHECK
# ============================================================

@app.get("/")
def root():

    return {
        "application": "Internship Resume Tailoring Agent",
        "version": "1.0",
        "status": "running",
        "playground": "/resume-agent/playground/"
    }


# ============================================================
# 12. LOCAL / RENDER SERVER
# ============================================================

if __name__ == "__main__":

    import uvicorn

    port = int(
        os.environ.get("PORT", 8000)
    )

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port
    )

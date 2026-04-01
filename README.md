# 🚀 Quick Commands

### One-Click Start (Mac)
The fastest way to get DeerFlow running. Handles setup, config, and Docker in one go:
```bash
cd repo && ./boom.sh
```

### Manual Start
```bash
cd repo && make docker-start
```

### ⚠️ System Requirements (Docker)
**DeerFlow development (Next.js 16 + Turbopack) is resource-intensive.**
- **Minimum Docker RAM:** 8GB (will be slow/unstable)
- **Recommended Docker RAM:** 12GB - 16GB
- **Global Settings:** Ensure your Docker Desktop (Settings -> Resources) is set to at least 12GB. If you see a "502 Bad Gateway" error, it usually means the frontend ran out of memory.

### Stop the Application
```bash
cd repo && make docker-stop
```

### Full Rebuild (Use if you change config or code)
```bash
cd repo && make docker-stop && make docker-init && make docker-start
```

### Fix Docker Network Conflict
If `make docker-start` fails with `Pool overlaps with other one on this address space`, run this to clean up stale containers and networks:
```bash
docker stop deer-flow-nginx deer-flow-gateway deer-flow-langgraph deer-flow-frontend 2>/dev/null; docker rm deer-flow-nginx deer-flow-gateway deer-flow-langgraph deer-flow-frontend 2>/dev/null; docker network rm docker_deer-flow-dev deer-flow-dev_deer-flow-dev 2>/dev/null; echo "Cleaned up"
```

### Docker Cleanup & Reset (Nuclear Option)
If the app is giving "Bad Gateway" or connection errors and regular restarts don't work, run this to completely wipe the DeerFlow Docker state and start fresh:
```bash
# 1. Stop and remove all DeerFlow containers
docker stop deer-flow-nginx deer-flow-gateway deer-flow-langgraph deer-flow-frontend 2>/dev/null
docker rm deer-flow-nginx deer-flow-gateway deer-flow-langgraph deer-flow-frontend 2>/dev/null

# 2. Remove the custom network
docker network rm deer-flow-dev_deer-flow-dev 2>/dev/null

# 3. Optional: Prune unused Docker data (Use with caution, clears all unused Docker data)
# docker system prune -f

# 4. Restart using the one-click script
./boom.sh
```
Then start again:
```bash
cd repo && make docker-start
```

---

# DeerFlow Local Setup Summary

The setup for the DeerFlow directory is complete and the repository is cloned into the repo folder.
I followed the setup guide to generate and modify the configuration files for a local environment.

## Completed Actions

1 Configuration Generation
I executed the make config command using python3.
This created the initial config.yaml and .env files.

2 Model Configuration
The local qwen model is now in config.yaml.
It points to the Ollama endpoint at http://host.docker.internal:11434/v1 for access within Docker.

3 Planner and Reporter
The planner and reporter sections are added to the configuration.
Both utilize the local qwen model.

4 Sandbox Isolation
The AioSandboxProvider is enabled for Docker based isolation.
Auto cleanup is active to maintain a clean environment.

5 Search Tools
The TavilySearch tool is updated to use the TAVILY_API_KEY environment variable.

6 Environment Variables
A placeholder for TAVILY_API_KEY is added to the .env file.

## Important Note on DeerFlow 2.0

DeerFlow 2.0 is a complete rewrite.
Internal structures and tool paths differ from previous versions.
I adjusted the paths to deerflow.community to ensure full compatibility with the current codebase.

## Prerequisites

Ensure Ollama is running on your host machine.
Pull the required model using the following command.
ollama pull qwen2.5:7b

Update the TAVILY_API_KEY in the .env file with your actual key if you wish to use web search.

## Built-in Web UI
DeerFlow comes with a functional web interface.
Once started, it is available locally at http://localhost:2026.
You can use this interface to enter research topics and view generated reports.

## 🧪 Recommended Research Prompt
Copy and paste this into DeerFlow to get an elite-level research report:

> I want you to act as an elite research analyst with deep experience in synthesizing complex information into clear, concise insights.
>
> Your task is to conduct a comprehensive research breakdown on the following topic:
>
> **[ Insert your topic here ]**
>
> Here’s how I want you to proceed:
>
> 1. **Overview:** Start with a brief, plain-English overview of the topic.
> 2. **Structure:** Break the topic into 3–5 major sub-topics or components.
> 3. **Deep Dive:** For each sub-topic, provide:
>    - A short definition or explanation.
>    - Key facts, trends, or recent developments.
>    - Any major debates or differing perspectives.
> 4. **Evidence:** Include notable data, statistics, or real-world examples where relevant.
> 5. **Resources:** Recommend 3–5 high-quality resources for further reading (articles, papers, videos, or tools).
> 6. **Smart Summary:** End with a 5-bullet point executive briefing for a fast but insightful grasp of the topic.
>
> **Guidelines:**
> - Write in a clear, structured format.
> - Prioritize relevance, accuracy, and clarity.
> - No fluff, just value. Act like you're preparing a research memo for a CEO or investor.


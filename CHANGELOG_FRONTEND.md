# Frontend and UI/UX Customization Log

This document tracks the modifications made to the DeerFlow 2.0 interface and backend to provide a streamlined, data-driven research environment.

## Backend Enhancements

### 1. System Statistics API
- **File**: `backend/app/gateway/routers/stats.py`
- **Endpoint**: `GET /api/stats`
- **Functionality**: Returns live JSON data for:
  - **RAM**: Total, used, available, and percentage.
  - **Model**: Identifies the primary active model from `config.yaml`.
  - **Agents**: Provides a status mapping (Idle/Busy) for core agents (Planner, Researcher, Coder).
- **Integration**: Registered in `backend/app/gateway/app.py`.

### 2. Dependency Management
- **File**: `backend/Dockerfile`
- **Change**: Added `python3-psutil` to the system packages to enable cross-platform memory monitoring inside the container.

## Frontend Components

### 1. Live Dashboard Component
- **File**: `frontend/src/components/workspace/dashboard.tsx`
- **Features**:
  - **Real-time Polling**: Fetches system stats every 2 seconds.
  - **Visual Progress Bar**: Displays RAM usage with dynamic styling.
  - **Model Monitoring**: Shows the exact model string being used by the backend.
  - **Agent Status Grid**: Lists core agents with color-coded status indicators (Green for Idle, Yellow for Busy).

### 2. Sidebar Reconstruction
- **File**: `frontend/src/components/workspace/workspace-sidebar.tsx`
- **Modifications**:
  - Integrated the `Dashboard` component into the primary sidebar content area.
  - Added a "Recent Chats" section header for better visual hierarchy.

## UI/UX Simplification (Minimalist Mode)

### 1. Navigation Cleanup
- **Removed**: `WorkspaceNavChatList` (Internal redundant navigation).
- **Removed**: `WorkspaceNavMenu` (The bottom settings/external links menu).

### 2. External Link Removal
- Removed all GitHub icons and repository links.
- Removed "Official Website" and "Contact Us" links.
- Removed "Report Issue" and "About" sections.
- Removed the Settings gear icon and associated dropdown to ensure a focused, "dead simple" chat interface.

## Current State
- **URL**: http://localhost:2026
- **Primary Model**: qwen2.5:7b
- **Environment**: Docker-orchestrated with AIO Sandbox enabled.

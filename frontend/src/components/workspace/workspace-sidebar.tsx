"use client";

import {
  Sidebar,
  SidebarHeader,
  SidebarContent,
  SidebarFooter,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar";

import { Dashboard } from "./dashboard";
import { RecentChatList } from "./recent-chat-list";
import { WorkspaceHeader } from "./workspace-header";

export function WorkspaceSidebar({
  ...props
}: React.ComponentProps<typeof Sidebar>) {
  const { open: isSidebarOpen } = useSidebar();
  return (
    <>
      <Sidebar variant="sidebar" collapsible="icon" {...props}>
        <SidebarHeader className="py-0">
          <WorkspaceHeader />
        </SidebarHeader>
        <SidebarContent>
          {isSidebarOpen && <Dashboard />}
          {isSidebarOpen && <div className="px-4 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Recent Chats</div>}
          {isSidebarOpen && <RecentChatList />}
        </SidebarContent>
        <SidebarFooter>
          {/* Footer removed for simplicity */}
        </SidebarFooter>
        <SidebarRail />
      </Sidebar>
    </>
  );
}

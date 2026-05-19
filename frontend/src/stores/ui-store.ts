import { create } from "zustand";
import type { Notification } from "@/types";

interface SidebarState {
  isCollapsed: boolean;
  toggle: () => void;
  collapse: () => void;
  expand: () => void;
}

interface NotificationsState {
  items: Notification[];
  unreadCount: number;
  add: (notification: Omit<Notification, "id" | "created_at" | "read">) => void;
  dismiss: (id: string) => void;
  markAllRead: () => void;
  clear: () => void;
}

interface ModalState {
  activeModal: string | null;
  modalData: unknown;
  open: (name: string, data?: unknown) => void;
  close: () => void;
}

interface UIState {
  sidebar: SidebarState;
  notifications: NotificationsState;
  modals: ModalState;
}

let notificationIdCounter = 0;

export const useUIStore = create<UIState>()((set) => ({
  sidebar: {
    isCollapsed: false,
    toggle: () =>
      set((state) => ({
        sidebar: {
          ...state.sidebar,
          isCollapsed: !state.sidebar.isCollapsed,
        },
      })),
    collapse: () =>
      set((state) => ({
        sidebar: { ...state.sidebar, isCollapsed: true },
      })),
    expand: () =>
      set((state) => ({
        sidebar: { ...state.sidebar, isCollapsed: false },
      })),
  },

  notifications: {
    items: [],
    unreadCount: 0,
    add: (notification) => {
      const newNotification: Notification = {
        ...notification,
        id: String(++notificationIdCounter),
        read: false,
        created_at: new Date().toISOString(),
      };
      set((state) => ({
        notifications: {
          ...state.notifications,
          items: [newNotification, ...state.notifications.items].slice(0, 50),
          unreadCount: state.notifications.unreadCount + 1,
        },
      }));
    },
    dismiss: (id: string) => {
      set((state) => {
        const item = state.notifications.items.find((n) => n.id === id);
        return {
          notifications: {
            ...state.notifications,
            items: state.notifications.items.filter((n) => n.id !== id),
            unreadCount: item?.read
              ? state.notifications.unreadCount
              : Math.max(0, state.notifications.unreadCount - 1),
          },
        };
      });
    },
    markAllRead: () => {
      set((state) => ({
        notifications: {
          ...state.notifications,
          items: state.notifications.items.map((n) => ({ ...n, read: true })),
          unreadCount: 0,
        },
      }));
    },
    clear: () => {
      set((state) => ({
        notifications: {
          ...state.notifications,
          items: [],
          unreadCount: 0,
        },
      }));
    },
  },

  modals: {
    activeModal: null,
    modalData: null,
    open: (name: string, data?: unknown) => {
      set((state) => ({
        modals: { ...state.modals, activeModal: name, modalData: data ?? null },
      }));
    },
    close: () => {
      set((state) => ({
        modals: { ...state.modals, activeModal: null, modalData: null },
      }));
    },
  },
}));

// Convenience selectors
export const useSidebar = () => useUIStore((s) => s.sidebar);
export const useNotifications = () => useUIStore((s) => s.notifications);
export const useModals = () => useUIStore((s) => s.modals);

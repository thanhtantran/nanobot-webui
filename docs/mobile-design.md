# Mobile Adaptation Design Plan

> Reference: NetEase Music mobile UI (bottom tab bar + full-screen content + slide-in panels)

---

## 1. Core Problems (Current State)

The app has **zero responsive design**. On a 390px (iPhone 12) viewport:

| Component | Issue |
|-----------|-------|
| Sidebar (192px) + Chat sidebar (208px) | Consumes 100%+ of screen width |
| Buttons `h-6 w-6` (24px) | Apple HIG requires 44×44px touch targets |
| Font `text-[11px]` in tool cards | Unreadable at mobile size |
| Code/table in messages | Overflows without horizontal scroll |
| No bottom tab bar | Nav buried in always-visible sidebar |

---

## 2. Layout Strategy

### Breakpoint Split

```
< 768px  →  Mobile layout (bottom tabs, full-screen panels, drawer)
≥ 768px  →  Desktop layout (current sidebar + split-pane)
```

### Mobile Navigation: Bottom Tab Bar

Replaces the left sidebar entirely on mobile. Inspired by the reference UI.

```
┌─────────────────────────────────────┐
│  Header (back button · title · ops) │  h-12
├─────────────────────────────────────┤
│                                     │
│           Page Content              │  flex-1
│                                     │
├─────────────────────────────────────┤
│  🏠 Dashboard │ 💬 Chat │ ⚙ Settings│  h-14 (safe-area-bottom)
└─────────────────────────────────────┘
```

Bottom tab items (mobile only):
- **Dashboard** — `LayoutDashboard`
- **Chat** — `MessageSquare` (with badge for unread)
- **Admin** (admin role only) — `Settings` → opens slide-up sheet with full admin menu

---

## 3. Page-by-Page Design

### 3.1 AppLayout

**Desktop** (unchanged): `Sidebar` (collapsible) + `<main>`

**Mobile**:
- Hide `Sidebar` completely
- Render `MobileBottomTabs` fixed at bottom
- `<main>` takes full width, `pb-14` to clear tabs

```tsx
// AppLayout.tsx concept
const isMobile = useMediaQuery("(max-width: 767px)");

<div className="flex h-screen overflow-hidden">
  {!isMobile && <Sidebar ... />}
  <main className={cn("flex-1 min-w-0", isMobile && "pb-[env(safe-area-inset-bottom)]")}>
    <Outlet />
  </main>
  {isMobile && <MobileBottomTabs />}
</div>
```

---

### 3.2 Chat Page (CRITICAL)

This is the most complex adaptation. Current layout is a horizontal split:

```
[aside 208px | gap 16px | ChatWindow flex-1]
```

**Mobile: Two-Screen Stack**

```
Screen A: Session List (full-width)
Screen B: Chat Window (full-width, slides in from right)
```

Navigation:
- Chat page root (`/chat`) → shows Session List
- Tap session → push to `/chat/:id` (full-screen chat window)
- Back button in Header → returns to Session List

**Session List (Mobile)**:

```
┌─────────────────────────────────┐
│ 🔍 Search...          [+]       │  h-12 sticky header
├─────────────────────────────────┤
│ ┌─────────────────────────────┐ │
│ │ 🤖  Session title           │ │  h-16
│ │     Last message preview... │ │
│ └─────────────────────────────┘ │
│ ┌─────────────────────────────┐ │
│ │ 🤖  Session title           │ │
│ │     Last message preview... │ │
│ └─────────────────────────────┘ │
└─────────────────────────────────┘
```

Style changes:
- Row height `h-16` (64px) vs desktop `h-12`
- Avatar `h-10 w-10` (40px) for better visibility
- Full-width rows, no column split
- Swipe-left to reveal delete (optional, phase 2)

**Chat Window (Mobile)**:

```
┌─────────────────────────────────┐
│ ← Session Name    [menu] [•••]  │  h-12 sticky
├─────────────────────────────────┤
│                                 │
│   Message bubbles               │
│     (full-width messages)       │
│                                 │
├─────────────────────────────────┤
│ [📎][🔧]  Type a message... [➤] │  min-h-12 input
│                      safe-area  │
└─────────────────────────────────┘
```

Changes:
- Message bubble `max-w-[85%]` on mobile (vs 78%)
- Avatar hidden on mobile to save space (or `h-6 w-6`)
- Tool toggle / attachment as icon-only buttons at start of input bar
- Send button `h-10 w-10` minimum for touch

---

### 3.3 Input Bar (Mobile)

Current desktop toolbar has 6+ buttons in a row. Mobile collapses it:

**Default state**:
```
[📎] [text input flex-1] [Send / Stop]
```

**Expanded state** (tap `📎` or `+`):
```
┌─────────────────────────────────┐
│ 📂 File    🔧 Tools   🧠 Think  │  slide-up from bottom
└─────────────────────────────────┘
```

Using a sheet/drawer for the extra actions keeps the main bar clean.

Touch target spec:
- All tap targets minimum **44×44px**
- Send button `h-11 w-11`
- Icon buttons `h-10 w-10` with padding

---

### 3.4 Message Bubbles (Mobile)

Changes:
| Property | Desktop | Mobile |
|----------|---------|--------|
| `max-w` | `78%` | `85%` |
| Avatar | `h-8 w-8` show | `h-6 w-6` or hide |
| Code font | `text-xs` (12px) | `text-[11px]` + horizontal scroll |
| Code block | no scroll | `overflow-x-auto` added |
| Table | raw | `overflow-x-auto` wrapper |
| Padding | `p-4` | `p-3` |
| Copy button | hover visible | always visible on touch |

---

### 3.5 Admin Pages (Channels, Tools, Users, etc.)

These pages are infrequent / admin-only. Mobile approach:

- Access via **"Admin" bottom tab** → opens a `Sheet` (slide-up panel) with the admin menu
- Tapping an admin item navigates full-screen
- Tables → switch to card list on mobile (`md:table`, mobile = stacked cards)
- Forms → full-screen modal sheets

---

## 4. Component Inventory

New components to build:

| Component | Description |
|-----------|-------------|
| `MobileBottomTabs` | Fixed bottom navigation bar with safe-area support |
| `MobileHeader` | Slim sticky header with back button, title, action buttons |
| `useIsMobile()` | Hook wrapping `window.matchMedia("(max-width: 767px)")` |
| `MobileAdminSheet` | Slide-up sheet listing admin nav items |

Modified components:

| Component | Change |
|-----------|--------|
| `AppLayout` | Conditional: Sidebar on md+, BottomTabs on mobile |
| `Chat.tsx` | `flex-col md:flex-row`, show only one pane on mobile |
| `ChatWindow.tsx` | Mobile header with back nav, adjusted padding |
| `MessageBubble.tsx` | max-w mobile 85%, code overflow scroll, copy always visible |
| `ChatInput.tsx` | Collapsed toolbar, larger touch targets |
| `Sidebar.tsx` | `hidden md:flex` |

---

## 5. CSS / Tailwind Additions

```css
/* index.css additions */

/* Prevent double-tap zoom on buttons */
button, a {
  touch-action: manipulation;
}

/* Safe area bottom padding utility */
.pb-safe {
  padding-bottom: env(safe-area-inset-bottom);
}
```

```ts
// tailwind.config.ts - add custom screen
screens: {
  'xs': '375px',  // iPhone SE
  // sm: 640, md: 768, lg: 1024, xl: 1280 (defaults kept)
}
```

---

## 6. Reference UI Mapping (NetEase Music)

| NetEase Pattern | Our Equivalent |
|-----------------|----------------|
| Bottom tab bar (5 tabs) | `MobileBottomTabs` (3-4 tabs) |
| Full-screen list → tap → full-screen detail | Session list → tap → chat window |
| Left sidebar (榜单 categories) → inline list | Admin menu → `MobileAdminSheet` slide-up |
| Search bar sticky at top | Search in session list header |
| Minimal top header with back + title + icons | `MobileHeader` |
| Red accent `#e0191b` tab indicator | Primary orange accent |

---

## 7. Implementation Phases

### Phase 1 — Layout Foundation (High value, low risk)
1. `useIsMobile()` hook
2. `MobileBottomTabs` component
3. `AppLayout`: hide Sidebar on mobile, show bottom tabs
4. `Chat.tsx`: single-pane switching (list ↔ window)
5. `Sidebar.tsx`: `hidden md:flex`

### Phase 2 — Chat UX (Core experience)
6. `MobileHeader` with back button inside ChatWindow
7. Input bar: larger touch targets + collapse secondary actions
8. MessageBubble: `max-w-[85%]`, code `overflow-x-auto`, always-visible copy

### Phase 3 — Polish
9. Admin pages → card list layout
10. `MobileAdminSheet`
11. Safe area insets (iPhone notch / home indicator)
12. `touch-action: manipulation` global
13. Scroll-to-bottom FAB when not at bottom

---

## 8. Non-Goals (Out of Scope)

- Swipe gestures (swipe to delete session, swipe back)
- Offline mode / message caching
- Push notifications
- Image/file preview lightbox
- Voice input

// Minimal typings for frappe-gantt 1.2.2 (the package ships none). Only what <ProjectGantt> uses.
declare module 'frappe-gantt' {
  export interface GanttTask {
    id: string
    name: string
    start: string
    end: string
    progress?: number
    dependencies?: string | string[]
    custom_class?: string
    [key: string]: unknown
  }

  export interface PopupContext {
    task: GanttTask
    get_title: () => HTMLElement
    get_subtitle: () => HTMLElement
    get_details: () => HTMLElement
  }

  export type ViewMode = 'Day' | 'Week' | 'Month' | 'Year'

  export interface GanttOptions {
    view_mode?: ViewMode
    language?: string
    readonly?: boolean
    readonly_dates?: boolean
    readonly_progress?: boolean
    move_dependencies?: boolean
    infinite_padding?: boolean
    today_button?: boolean
    scroll_to?: 'today' | 'start' | 'end' | string | null
    popup_on?: 'click' | 'hover'
    popup?: false | ((ctx: PopupContext) => void | false | string)
    on_click?: (task: GanttTask) => void
    on_double_click?: (task: GanttTask) => void
    on_date_change?: (task: GanttTask, start: Date, end: Date) => void
    on_progress_change?: (task: GanttTask, progress: number) => void
    on_view_change?: (mode: unknown) => void
  }

  export default class Gantt {
    constructor(wrapper: HTMLElement | SVGElement | string, tasks: GanttTask[], options?: GanttOptions)
    options: GanttOptions
    setup_tasks(tasks: GanttTask[]): void
    change_view_mode(mode: ViewMode, maintain_pos?: boolean): void
    refresh(tasks: GanttTask[]): void
    clear(): void
  }
}

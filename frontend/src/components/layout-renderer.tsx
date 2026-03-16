import type { LayoutComponent } from '../types'
import { Header } from './header'
import { StatCard } from './stat-card'
import { ExerciseCard } from './exercise-card'
import { SetLogger } from './set-logger'
import { RestTimer } from './rest-timer'
import { TextBlock } from './text-block'
import { VideoPrompt } from './video-prompt'
import { ChartComponent } from './chart'
import { ActionButton } from './action-button'
import { ChatBubble } from './chat-bubble'

const COMPONENT_MAP: Record<string, React.FC<any>> = {
  header: Header, stat_card: StatCard, exercise_card: ExerciseCard,
  set_logger: SetLogger, rest_timer: RestTimer, text_block: TextBlock,
  video_prompt: VideoPrompt, chart: ChartComponent, action_button: ActionButton,
  chat_bubble: ChatBubble,
}

export function LayoutRenderer({ layout }: { layout: LayoutComponent[] }) {
  return (
    <div className="layout">
      {layout.map((component, i) => {
        const Component = COMPONENT_MAP[component.type]
        if (!Component) return null
        return <Component key={i} {...component} />
      })}
    </div>
  )
}

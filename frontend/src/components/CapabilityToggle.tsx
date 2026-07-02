import { clsx } from 'clsx'
import type { CapabilityConfig, CapabilityKey, CapabilityMode } from '@/types'
import { CAPABILITY_META } from '@/types'

interface Props {
  config: CapabilityConfig
  onChange: (capability: CapabilityKey, mode: CapabilityMode, enabled: boolean) => void
  disabled?: boolean
}

const MODE_OPTIONS: { value: CapabilityMode; label: string; description: string }[] = [
  { value: 'off', label: 'Off', description: 'Disabled' },
  { value: 'assisted', label: 'Assisted', description: 'Creates PRs for review' },
  { value: 'autopilot', label: 'Autopilot', description: 'Merges automatically' },
]

export function CapabilityToggle({ config, onChange, disabled }: Props) {
  const meta = CAPABILITY_META[config.capability]

  const handleModeChange = (mode: CapabilityMode) => {
    onChange(config.capability, mode, mode !== 'off')
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-start gap-3">
        <span className="text-2xl" role="img" aria-label={meta.label}>
          {meta.icon}
        </span>
        <div>
          <h3 className="font-semibold text-gray-900">{meta.label}</h3>
          <p className="text-sm text-gray-500">{meta.description}</p>
        </div>
      </div>

      <div className="flex gap-2">
        {MODE_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            disabled={disabled}
            onClick={() => handleModeChange(opt.value)}
            title={opt.description}
            className={clsx(
              'flex-1 rounded-md px-3 py-2 text-xs font-medium transition-colors',
              config.mode === opt.value && config.enabled !== false
                ? opt.value === 'autopilot'
                  ? 'bg-indigo-600 text-white'
                  : opt.value === 'assisted'
                    ? 'bg-amber-500 text-white'
                    : 'bg-gray-200 text-gray-700'
                : 'bg-gray-100 text-gray-500 hover:bg-gray-200',
              disabled && 'cursor-not-allowed opacity-50',
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  )
}

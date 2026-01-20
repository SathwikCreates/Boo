import React, { useState } from 'react'
import { Button } from './button'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { 
  format, 
  startOfMonth, 
  endOfMonth, 
  startOfWeek, 
  endOfWeek, 
  addDays, 
  addMonths, 
  subMonths, 
  isSameMonth, 
  isSameDay,
  isAfter,
  parseISO 
} from 'date-fns'

interface CalendarProps {
  selected?: string
  onSelect: (date: string) => void
  disabled?: boolean
  className?: string
  maxDate?: Date
}

export function Calendar({ selected, onSelect, disabled = false, className = '', maxDate }: CalendarProps) {
  const [currentMonth, setCurrentMonth] = useState(() => {
    if (selected) {
      try {
        return parseISO(selected)
      } catch {
        return new Date()
      }
    }
    return new Date()
  })

  const selectedDate = selected ? parseISO(selected) : null

  const nextMonth = () => {
    setCurrentMonth(addMonths(currentMonth, 1))
  }

  const prevMonth = () => {
    setCurrentMonth(subMonths(currentMonth, 1))
  }

  const renderCalendar = () => {
    const monthStart = startOfMonth(currentMonth)
    const monthEnd = endOfMonth(monthStart)
    const startDate = startOfWeek(monthStart)
    const endDate = endOfWeek(monthEnd)

    const dateFormat = "d"
    const rows = []

    let days = []
    let day = startDate
    let formattedDate = ""

    while (day <= endDate) {
      for (let i = 0; i < 7; i++) {
        formattedDate = format(day, dateFormat)
        const cloneDay = day
        const isCurrentMonth = isSameMonth(day, monthStart)
        const isSelected = selectedDate && isSameDay(day, selectedDate)
        const isToday = isSameDay(day, new Date())
        const isFutureDate = maxDate && isAfter(day, maxDate)

        days.push(
          <button
            key={day.toString()}
            onClick={() => !disabled && !isFutureDate && onSelect(format(cloneDay, 'yyyy-MM-dd'))}
            disabled={disabled || !isCurrentMonth || isFutureDate}
            className={`
              h-9 w-9 text-sm rounded-md flex items-center justify-center transition-all duration-200 font-medium
              ${!isCurrentMonth 
                ? 'text-muted-foreground/20 cursor-not-allowed' 
                : isFutureDate
                ? 'text-muted-foreground/40 cursor-not-allowed opacity-50'
                : 'text-white hover:bg-muted/60 cursor-pointer hover:scale-105'
              }
              ${isSelected 
                ? 'bg-gradient-to-br from-blue-500 to-purple-600 text-white hover:from-blue-600 hover:to-purple-700 font-bold shadow-lg scale-105 border-2 border-purple-400' 
                : ''
              }
              ${isToday && !isSelected 
                ? 'bg-muted/40 border-2 border-purple-400 font-bold text-purple-400' 
                : ''
              }
              ${disabled || isFutureDate ? 'opacity-50 cursor-not-allowed' : ''}
            `}
          >
            {formattedDate}
          </button>
        )
        day = addDays(day, 1)
      }
      rows.push(
        <div className="grid grid-cols-7 gap-1.5" key={day.toString()}>
          {days}
        </div>
      )
      days = []
    }
    return <div className="space-y-1.5">{rows}</div>
  }

  return (
    <div className={`bg-card border border-border rounded-lg p-6 w-[280px] ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={prevMonth}
          disabled={disabled}
          className="h-9 w-9 p-0 text-white hover:bg-muted/50 rounded-md"
        >
          <ChevronLeft className="h-5 w-5" />
        </Button>
        
        <h2 className="text-white font-semibold text-base px-2">
          {format(currentMonth, 'MMMM yyyy')}
        </h2>
        
        <Button
          variant="ghost"
          size="sm"
          onClick={nextMonth}
          disabled={disabled}
          className="h-9 w-9 p-0 text-white hover:bg-muted/50 rounded-md"
        >
          <ChevronRight className="h-5 w-5" />
        </Button>
      </div>

      {/* Weekday Headers */}
      <div className="grid grid-cols-7 gap-1 mb-3">
        {['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map((day) => (
          <div key={day} className="h-9 w-9 flex items-center justify-center">
            <span className="text-sm font-semibold text-muted-foreground">{day}</span>
          </div>
        ))}
      </div>

      {/* Calendar Grid */}
      {renderCalendar()}
    </div>
  )
}
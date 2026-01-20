import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'

interface Word {
  text: string
  value: number
  size?: number
  x?: number
  y?: number
  rotate?: number
}

interface WordCloudProps {
  words: Word[]
  onWordClick?: (word: Word) => void
  width?: number
  height?: number
}

function WordCloud({ words, onWordClick, width = 800, height = 400 }: WordCloudProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [dimensions, setDimensions] = useState({ width, height })
  const [processedWords, setProcessedWords] = useState<Word[]>([])

  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect()
        setDimensions({
          width: rect.width || width,
          height: rect.height || height
        })
      }
    }

    updateDimensions()
    window.addEventListener('resize', updateDimensions)
    return () => window.removeEventListener('resize', updateDimensions)
  }, [width, height])

  useEffect(() => {
    if (words.length === 0) return

    // Calculate font sizes based on word values
    const maxValue = Math.max(...words.map(w => w.value))
    const minValue = Math.min(...words.map(w => w.value))
    const sizeScale = (value: number) => {
      const normalized = (value - minValue) / (maxValue - minValue || 1)
      return 14 + normalized * 50 // Font size between 14 and 64
    }

    // Simple spiral placement algorithm
    const placed: Word[] = []
    const center = { x: dimensions.width / 2, y: dimensions.height / 2 }
    
    // Sort words by value (largest first)
    const sortedWords = [...words].sort((a, b) => b.value - a.value)
    
    sortedWords.forEach((word, index) => {
      const size = sizeScale(word.value)
      const textWidth = word.text.length * size * 0.6 // Approximate width
      const textHeight = size
      
      // Try to place word using spiral pattern
      let isPlaced = false
      let angle = 0
      let radius = 0
      const angleStep = 0.1
      const radiusStep = 2
      
      while (!isPlaced && radius < Math.max(dimensions.width, dimensions.height)) {
        const x = center.x + radius * Math.cos(angle)
        const y = center.y + radius * Math.sin(angle)
        
        // Check if position is within bounds
        const halfWidth = textWidth / 2
        const halfHeight = textHeight / 2
        
        if (x - halfWidth > 0 && 
            x + halfWidth < dimensions.width &&
            y - halfHeight > 0 && 
            y + halfHeight < dimensions.height) {
          
          // Check for overlaps with already placed words
          let overlaps = false
          for (const placedWord of placed) {
            const dx = Math.abs(x - placedWord.x!)
            const dy = Math.abs(y - placedWord.y!)
            const minDistX = (textWidth + (placedWord.text.length * placedWord.size! * 0.6)) / 2
            const minDistY = (textHeight + placedWord.size!) / 2
            
            if (dx < minDistX && dy < minDistY) {
              overlaps = true
              break
            }
          }
          
          if (!overlaps) {
            placed.push({
              ...word,
              size,
              x,
              y,
              rotate: index % 3 === 0 ? -90 : 0 // Some vertical words
            })
            isPlaced = true
          }
        }
        
        angle += angleStep
        radius += radiusStep * angleStep
      }
    })
    
    setProcessedWords(placed)
  }, [words, dimensions])

  const getWordColor = (index: number) => {
    const colors = ['#8b5cf6', '#ec4899', '#3b82f6', '#10b981', '#f59e0b']
    return colors[index % colors.length]
  }

  return (
    <div ref={containerRef} className="w-full h-full relative">
      <svg width={dimensions.width} height={dimensions.height} className="w-full h-full">
        <g>
          {processedWords.map((word, index) => (
            <motion.text
              key={word.text}
              x={word.x}
              y={word.y}
              fontSize={word.size}
              fontWeight="600"
              fontFamily="Inter, system-ui, sans-serif"
              fill={getWordColor(index)}
              textAnchor="middle"
              alignmentBaseline="middle"
              transform={`rotate(${word.rotate || 0} ${word.x} ${word.y})`}
              className="cursor-pointer select-none"
              onClick={() => onWordClick?.(word)}
              initial={{ opacity: 0, scale: 0 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: index * 0.02, duration: 0.3 }}
              whileHover={{ scale: 1.1 }}
            >
              {word.text}
            </motion.text>
          ))}
        </g>
      </svg>
    </div>
  )
}

export default WordCloud
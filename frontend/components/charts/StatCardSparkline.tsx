'use client'

import { Area, AreaChart, ResponsiveContainer } from 'recharts'
import { directionHex, type Direction } from '../../lib/financialTone'

interface StatCardSparklineProps {
    data: Array<{ i: number; val: number }>
    direction: Direction
}

export default function StatCardSparkline({ data, direction }: StatCardSparklineProps) {
    // Calm, single-tone trend: mint when up, muted slate otherwise — no casino red/green.
    const color = directionHex[direction]

    return (
        <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data}>
                <Area
                    type="monotone"
                    dataKey="val"
                    stroke={color}
                    fill={color}
                    fillOpacity={0.12}
                    strokeWidth={2}
                    isAnimationActive={false}
                />
            </AreaChart>
        </ResponsiveContainer>
    )
}

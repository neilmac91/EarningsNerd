'use client'

import { Area, AreaChart, ResponsiveContainer } from 'recharts'

interface StatCardSparklineProps {
    data: Array<{ i: number; val: number }>
    isNegative: boolean
}

export default function StatCardSparkline({ data, isNegative }: StatCardSparklineProps) {
    const strokeColor = isNegative ? '#e11d48' : '#059669'
    const fillColor = isNegative ? '#ffe4e6' : '#d1fae5'

    return (
        <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data}>
                <Area
                    type="monotone"
                    dataKey="val"
                    stroke={strokeColor}
                    fill={fillColor}
                    strokeWidth={2}
                    isAnimationActive={false}
                />
            </AreaChart>
        </ResponsiveContainer>
    )
}

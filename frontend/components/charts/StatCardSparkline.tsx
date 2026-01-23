'use client'

import { Area, AreaChart, ResponsiveContainer } from 'recharts'

interface StatCardSparklineProps {
    data: Array<{ i: number; val: number }>
    isNegative: boolean
}

export default function StatCardSparkline({ data, isNegative }: StatCardSparklineProps) {
    return (
        <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data}>
                <Area
                    type="monotone"
                    dataKey="val"
                    stroke={isNegative ? '#e11d48' : '#059669'}
                    fill={isNegative ? '#ffe4e6' : '#d1fae5'}
                    strokeWidth={2}
                    isAnimationActive={false}
                />
            </AreaChart>
        </ResponsiveContainer>
    )
}

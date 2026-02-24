import { useEffect, useState, useRef } from "react";

interface NumberTickerProps {
    value: number;
    precision?: number;
    className?: string;
    prefix?: string;
    suffix?: string;
    duration?: number; // ms
}

export const NumberTicker = ({
    value,
    precision = 2,
    className = "",
    prefix = "",
    suffix = "",
    duration = 500
}: NumberTickerProps) => {
    const [displayValue, setDisplayValue] = useState(value);
    const startValue = useRef(value);
    const targetValue = useRef(value);
    const startTime = useRef<number | null>(null);
    const reqId = useRef<number | null>(null);

    useEffect(() => {
        // Update target
        startValue.current = displayValue;
        targetValue.current = value;
        startTime.current = null;

        const animate = (time: number) => {
            if (!startTime.current) startTime.current = time;
            const progress = Math.min((time - startTime.current) / duration, 1);

            // Ease out cubic function: 1 - (1 - x)^3
            const ease = 1 - Math.pow(1 - progress, 3);

            const current = startValue.current + (targetValue.current - startValue.current) * ease;
            setDisplayValue(current);

            if (progress < 1) {
                reqId.current = requestAnimationFrame(animate);
            }
        };

        reqId.current = requestAnimationFrame(animate);

        return () => {
            if (reqId.current) cancelAnimationFrame(reqId.current);
        };
    }, [value, duration]);

    return (
        <span className={className}>
            {prefix}{displayValue.toFixed(precision)}{suffix}
        </span>
    );
};

import { useEffect, useRef, useCallback } from 'react';

/**
 * Custom hook for generating synthesized sound effects using the Web Audio API.
 * Provides `playIncrease` ("Ding Dong") and `playDecrease` ("Coin Splash") functions.
 * No external audio files required.
 */
export const useSoundEffects = () => {
    const audioCtxRef = useRef<AudioContext | null>(null);

    // Initialize AudioContext on first interaction or mount
    useEffect(() => {
        const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
        if (!AudioContextClass) return;

        // Create context but keep suspended until interaction
        audioCtxRef.current = new AudioContextClass();

        const resumeAudio = () => {
            if (audioCtxRef.current?.state === 'suspended') {
                audioCtxRef.current.resume();
            }
            window.removeEventListener('click', resumeAudio);
            window.removeEventListener('keydown', resumeAudio);
        };

        window.addEventListener('click', resumeAudio);
        window.addEventListener('keydown', resumeAudio);

        return () => {
            window.removeEventListener('click', resumeAudio);
            window.removeEventListener('keydown', resumeAudio);
            audioCtxRef.current?.close();
        };
    }, []);

    // Helper: Play a tone with envelope
    const playTone = (freq: number, type: OscillatorType, duration: number, startTime: number, volume: number) => {
        if (!audioCtxRef.current) return;
        const ctx = audioCtxRef.current;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = type;
        osc.frequency.setValueAtTime(freq, startTime);

        // Envelope: Attack -> Decay
        gain.gain.setValueAtTime(0, startTime);
        gain.gain.linearRampToValueAtTime(volume, startTime + 0.01);
        gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration);

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.start(startTime);
        osc.stop(startTime + duration + 0.1);
    };

    /**
     * "叮铃" - 开仓音效
     * 快速 3 连击高频 sine 波
     */
    const playIncrease = useCallback(() => {
        if (!audioCtxRef.current) return;
        const ctx = audioCtxRef.current;
        const t = ctx.currentTime;

        const notes = [3520, 4186, 3520]; // A7, C8, A7
        notes.forEach((freq, i) => {
            playTone(freq, 'sine', 0.15, t + i * 0.08, 0.12);
        });
    }, []);

    /**
     * "Coin Splash / Money" - Used for Position Decrease (Closing/Profit)
     * Rapid sequence of high-pitched metallic pings
     */
    const playDecrease = useCallback(() => {
        if (!audioCtxRef.current) return;
        const ctx = audioCtxRef.current;
        const t = ctx.currentTime;

        // Simulate multiple coins hitting together
        const coinCount = 5;
        for (let i = 0; i < coinCount; i++) {
            // Randomize pitch and timing slightly
            const pitch = 2000 + Math.random() * 2000; // 2kHz - 4kHz range
            const offset = (Math.random() * 0.15); // 0 - 150ms spread
            const dur = 0.1 + Math.random() * 0.1; // Short ping

            playTone(pitch, 'sine', dur, t + offset, 0.08);
            // Add metallic overtone
            playTone(pitch * 1.5, 'square', dur * 0.5, t + offset, 0.02);
        }
    }, []);

    return { playIncrease, playDecrease };
};

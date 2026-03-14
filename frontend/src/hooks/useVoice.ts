import { useState, useRef, useCallback } from 'react';

interface SpeechRecognitionEvent {
  results: { [index: number]: { [index: number]: { transcript: string } } };
  resultIndex: number;
}

const SpeechRecognition =
  (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

export function useVoice() {
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [transcript, setTranscript] = useState('');
  const recognitionRef = useRef<any>(null);
  const supported = !!SpeechRecognition;

  const startListening = useCallback((onResult?: (text: string) => void, existingText?: string) => {
    if (!SpeechRecognition) return;
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-IN';

    const prefix = existingText?.trim() || '';

    recognition.onstart = () => setListening(true);

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let finalTranscript = '';
      for (let i = event.resultIndex; i < Object.keys(event.results).length; i++) {
        finalTranscript += event.results[i][0].transcript;
      }
      setTranscript(finalTranscript);
      const combined = prefix ? prefix + '\n' + finalTranscript : finalTranscript;
      onResult?.(combined);
    };

    recognition.onend = () => setListening(false);
    recognition.onerror = () => setListening(false);

    recognitionRef.current = recognition;
    recognition.start();
  }, []);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    setListening(false);
  }, []);

  const speak = useCallback((text: string) => {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const cleaned = text.replace(/[*#_`]/g, '').replace(/\n+/g, '. ');
    const utterance = new SpeechSynthesisUtterance(cleaned);
    utterance.lang = 'en-IN';
    utterance.rate = 1.05;
    utterance.pitch = 1;
    utterance.onstart = () => setSpeaking(true);
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    window.speechSynthesis.speak(utterance);
  }, []);

  const stopSpeaking = useCallback(() => {
    window.speechSynthesis?.cancel();
    setSpeaking(false);
  }, []);

  return { listening, speaking, transcript, startListening, stopListening, speak, stopSpeaking, supported };
}

import { useRef, useEffect, useCallback } from 'react';
import { useNairaStore } from '../state/useNairaStore';

/**
 * Custom hook for Neural Ears (Speech-to-Text via Web Speech API).
 * Controls window.SpeechRecognition / window.webkitSpeechRecognition,
 * manages isMicListening state, updates avatarMode, and sets spokenText upon speech resolution.
 */
export const useNeuralMic = () => {
  const isMicListening = useNairaStore((state) => state.isMicListening);
  const setMicListening = useNairaStore((state) => state.setMicListening);
  const setSpokenText = useNairaStore((state) => state.setSpokenText);
  const setAvatarMode = useNairaStore((state) => state.setAvatarMode);

  const recognitionRef = useRef(null);

  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = 'en-US';

      recognition.onstart = () => {
        setMicListening(true);
        setAvatarMode('listening');
      };

      recognition.onresult = (event) => {
        const transcript = event.results[0]?.[0]?.transcript;
        if (transcript) {
          setSpokenText(transcript);
        }
        setMicListening(false);
      };

      recognition.onerror = (event) => {
        console.warn('[NeuralMic] Speech recognition error:', event.error);
        setMicListening(false);
        setAvatarMode('idle');
      };

      recognition.onend = () => {
        setMicListening(false);
      };

      recognitionRef.current = recognition;
    } else {
      console.warn('[NeuralMic] Web Speech Recognition is not supported in this browser.');
    }

    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch (e) {
          // ignore
        }
      }
    };
  }, [setMicListening, setSpokenText, setAvatarMode]);

  const startListening = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.start();
      } catch (err) {
        // If already active or error, stop and restart
        try {
          recognitionRef.current.stop();
          recognitionRef.current.start();
        } catch (e) {
          console.error('[NeuralMic] Could not start speech recognition:', e);
        }
      }
    } else {
      console.warn('[NeuralMic] Speech recognition not initialized or unsupported.');
    }
  }, []);

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (err) {
        console.error('[NeuralMic] Stop listening error:', err);
      }
    }
    setMicListening(false);
    setAvatarMode('idle');
  }, [setMicListening, setAvatarMode]);

  const toggleListening = useCallback(() => {
    if (isMicListening) {
      stopListening();
    } else {
      startListening();
    }
  }, [isMicListening, startListening, stopListening]);

  return {
    isMicListening,
    startListening,
    stopListening,
    toggleListening,
  };
};

export default useNeuralMic;

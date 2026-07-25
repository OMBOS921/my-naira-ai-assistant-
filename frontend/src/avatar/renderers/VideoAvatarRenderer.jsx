import React, { useRef, useEffect } from 'react';

/**
 * Video-to-Live2D Adapter Renderer
 * Renders avatar video loops corresponding to current avatar state mode.
 */

const MODE_VIDEO_MAP = {
  idle: '/avatar/idle.mp4',
  greeting: '/avatar/talking.mp4',
  listening: '/avatar/listening.mp4',
  speaking: '/avatar/talking.mp4',
  thinking: '/avatar/thinking.mp4',
};

export const VideoAvatarRenderer = ({ mode = 'idle', className = '' }) => {
  const videoRef = useRef(null);

  const currentVideoSrc = MODE_VIDEO_MAP[mode] || MODE_VIDEO_MAP.idle;

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    // Update src and trigger play smoothly on mode changes
    if (video.src !== window.location.origin + currentVideoSrc) {
      video.src = currentVideoSrc;
      video.load();
      const playPromise = video.play();
      if (playPromise !== undefined) {
        playPromise.catch((err) => {
          // Handle autoplay restriction or transition interrupt gracefully
          console.debug('Video playback notice:', err?.message || err);
        });
      }
    }
  }, [mode, currentVideoSrc]);

  return (
    <div className={`relative flex items-center justify-center overflow-hidden rounded-full ${className}`}>
      <video
        ref={videoRef}
        src={currentVideoSrc}
        muted
        loop
        playsInline
        autoPlay
        className="w-full h-full object-cover rounded-full"
      />
    </div>
  );
};

export default VideoAvatarRenderer;

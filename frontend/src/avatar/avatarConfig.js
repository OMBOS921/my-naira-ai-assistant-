import VideoAvatarRenderer from './renderers/VideoAvatarRenderer';

/**
 * Avatar Adapter Strategy Registry & Config
 * Allows swapping avatar renderers (e.g. video, live2d, canvas) seamlessly.
 */
export const ACTIVE_AVATAR_RENDERER = 'video';

export const AVATAR_RENDERERS = {
  video: VideoAvatarRenderer,
};

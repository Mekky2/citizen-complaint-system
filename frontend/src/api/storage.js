import client from './client';

export const UPLOADS_ENABLED = true;

export async function uploadFile(ticketId, file) {
  const formData = new FormData();
  formData.append('file', file, file.name);

  const response = await client.post(
    `/tickets/${ticketId}/media/upload`,
    formData
  );

  return response.data;
}

export const mediaTypeOf = (file) => {
  if (file.type.startsWith('video/')) return 'video';
  if (file.type.startsWith('audio/')) return 'audio';
  return 'image';
};

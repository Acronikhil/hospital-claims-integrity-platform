import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

const client = axios.create({ baseURL });

export const getClaims = () => client.get("/claims").then((res) => res.data);

export const getClaim = (claimId) => client.get(`/claims/${claimId}`).then((res) => res.data);

export const uploadClaimDocuments = (files) => {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  return client
    .post("/claims/upload", formData, { headers: { "Content-Type": "multipart/form-data" } })
    .then((res) => res.data);
};

export const decideClaim = (claimId, payload) =>
  client.post(`/claims/${claimId}/decision`, payload).then((res) => res.data);

export default client;

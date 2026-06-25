import { apiGet } from "./client";

export async function fetchOverview() {
  return apiGet("/api/overview");
}
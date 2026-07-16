export type BudgetLevel = 'low' | 'mid' | 'high'
export type HotelType = '经济型' | '舒适型' | '豪华型'

export interface TripRequest {
  destination: string
  start_date: string
  end_date?: string | null
  days?: number | null
  budget_level: BudgetLevel
  interests: string[]
  hotel_type: HotelType
}

export interface GeoPoint {
  lng: number | null
  lat: number | null
}

export interface Attraction {
  name: string
  address?: string | null
  location?: GeoPoint | null
  rating?: number | null
  image_url?: string | null
  ticket_price?: number | null
  tags?: string[]
  source?: string | null
}

export interface Hotel {
  name: string
  address?: string | null
  location?: GeoPoint | null
  price_per_night?: number | null
  star?: number | null
  image_url?: string | null
  source?: string | null
}

export interface DailyWeather {
  date: string
  day_desc?: string | null
  temp_min?: number | null
  temp_max?: number | null
  precipitation?: number | null
  wind?: string | null
  source?: string | null
}

export interface ItineraryDay {
  date: string
  index: number
  attractions: Attraction[]
  hotel: Hotel | null
  weather: DailyWeather | null
}

export interface BudgetBreakdown {
  ticket: number
  hotel: number
  food: number
  transport: number
  total: number
  currency: string
}

export interface Itinerary {
  days: ItineraryDay[]
  budget: BudgetBreakdown
  notes: string[]
  is_demo: boolean
  sources: string[]
}

export interface PlanAccepted {
  task_id: string
  request_id: string
  status: 'accepted'
}

export interface PlanResult {
  request_id: string
  task_id: string
  status: 'success' | 'partial' | 'failed'
  itinerary?: Itinerary
  condition_summary?: string
  query_time?: string
  hints?: string
  error_code?: string
  error_message?: string
}

export interface ApiError {
  request_id?: string
  error: {
    code: string
    message: string
  }
}

export interface HealthResponse {
  status: string
  app: Record<string, unknown>
  dependencies: { name: string; available: boolean; detail: string }[]
  timestamp: string
}

export interface MetricsBucket {
  total: number
  success: number
  failed: number
  timeout: number
  avg_ms: number
}

export interface MetricsSnapshot {
  total: number
  by_type: Record<string, MetricsBucket>
}

export interface ClientConfig {
  amap_js_key: string | null
  has_amap_js_key: boolean
}
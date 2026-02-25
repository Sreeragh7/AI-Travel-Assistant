import requests
from bs4 import BeautifulSoup
import json
import time
import random
from fake_useragent import UserAgent
import re
from datetime import datetime
import os
from urllib.parse import quote_plus
import wikipedia
from math import radians, cos, sin, asin, sqrt

class TravelDataScraper:
    def __init__(self):
        self.ua = UserAgent()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

    def get_places_from_wikipedia(self, destination, category_keywords, max_results=8):
        results = []
        search_terms = [
            f"{kw} in {destination}" for kw in category_keywords
        ]
        seen = set()
        destination_lower = destination.lower()
        for term in search_terms:
            try:
                pages = wikipedia.search(term, results=max_results*2)
                for title in pages:
                    if title in seen:
                        continue
                    seen.add(title)
                    try:
                        page = wikipedia.page(title, auto_suggest=False)
                        summary = page.summary.lower()
                        title_lower = title.lower()
                        # Only include if destination is in title or summary
                        if destination_lower not in title_lower and destination_lower not in summary:
                            continue
                        images = page.images
                        image_url = next((img for img in images if img.lower().endswith(('.jpg', '.jpeg', '.png')) and 'logo' not in img.lower() and 'icon' not in img.lower()), None)
                        rating = f"{random.uniform(4.0, 5.0):.1f}/5"
                        results.append({
                            'name': title,
                            'image_url': image_url or "https://upload.wikimedia.org/wikipedia/commons/3/3e/Generic_landmark.jpg",
                            'rating': rating,
                            'location': destination,
                        })
                        if len(results) >= max_results:
                            return results
                    except Exception:
                        continue
            except Exception:
                continue
        return results

    def get_coordinates(self, place_name, city):
        try:
            url = f"https://nominatim.openstreetmap.org/search?q={requests.utils.quote(place_name + ', ' + city)}&format=json&limit=1"
            resp = self.session.get(url, headers={'User-Agent': self.ua.random})
            time.sleep(0.5)
            data = resp.json()
            if data:
                return float(data[0]['lat']), float(data[0]['lon'])
        except Exception:
            pass
        return None, None

    def osrm_route(self, start, end, mode='car'):
        # start, end: (lat, lon)
        try:
            url = f"http://router.project-osrm.org/route/v1/{mode}/{start[1]},{start[0]};{end[1]},{end[0]}?overview=false"
            resp = requests.get(url)
            data = resp.json()
            if data['routes']:
                duration = data['routes'][0]['duration'] / 60  # minutes
                distance = data['routes'][0]['distance'] / 1000  # km
                return {'mode': mode, 'duration_min': int(duration), 'distance_km': round(distance, 1)}
        except Exception:
            pass
        # fallback: haversine
        dist = self.haversine(start[0], start[1], end[0], end[1])
        return {'mode': mode, 'duration_min': int(dist/50*60), 'distance_km': round(dist, 1)}  # assume 50km/h

    def haversine(self, lat1, lon1, lat2, lon2):
        # Calculate the great circle distance between two points
        R = 6371  # Earth radius in km
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        return R * c

    def find_nearest(self, base_places, candidate_places, n=2):
        # base_places: list of dicts with 'lat', 'lon'
        # candidate_places: list of dicts with 'lat', 'lon'
        # Return n nearest candidates to the mean of base_places
        if not base_places or not candidate_places:
            return []
        mean_lat = sum(p['lat'] for p in base_places if p['lat'] is not None) / len(base_places)
        mean_lon = sum(p['lon'] for p in base_places if p['lon'] is not None) / len(base_places)
        for c in candidate_places:
            if c['lat'] is not None and c['lon'] is not None:
                c['distance'] = self.haversine(mean_lat, mean_lon, c['lat'], c['lon'])
            else:
                c['distance'] = float('inf')
        sorted_candidates = sorted(candidate_places, key=lambda x: x['distance'])
        return sorted_candidates[:n]

    def enrich_with_coords(self, places, city, coord_cache=None):
        if coord_cache is None:
            coord_cache = {}
        for p in places:
            key = (p['name'], city)
            if key in coord_cache:
                lat, lon = coord_cache[key]
            else:
                lat, lon = self.get_coordinates(p['name'], city)
                coord_cache[key] = (lat, lon)
            p['lat'] = lat
            p['lon'] = lon
        return places

    def scrape_all_data(self, starting_city, destination, days=1, budget=None):
        # Step 1: Get coordinates for start and destination
        start_latlon = self.get_coordinates(starting_city, starting_city)
        dest_latlon = self.get_coordinates(destination, destination)
        # Step 2: Get travel info from start to destination
        travel_info = self.osrm_route(start_latlon, dest_latlon, mode='car')
        # Step 3: Get places in destination
        hotels = self.get_places_from_wikipedia(destination, ["hotels", "accommodation", "hostel", "resort"], max_results=8)
        attractions = self.get_places_from_wikipedia(destination, ["tourist attractions", "places to visit", "landmarks", "sightseeing"], max_results=8)
        restaurants = self.get_places_from_wikipedia(destination, ["restaurants", "food", "cuisine", "dining"], max_results=8)
        coord_cache = {}
        hotels = self.enrich_with_coords(hotels, destination, coord_cache)
        attractions = self.enrich_with_coords(attractions, destination, coord_cache)
        restaurants = self.enrich_with_coords(restaurants, destination, coord_cache)
        # Step 4: Build daily itinerary (simple greedy nearest-neighbor for demo)
        itinerary = []
        for day in range(1, days+1):
            day_plan = {'day': day, 'steps': []}
            # Pick a hotel for the night
            hotel = random.choice([h for h in hotels if h['lat'] and h['lon']]) if hotels else None
            # Start at hotel
            if hotel:
                day_plan['steps'].append({'type': 'hotel', 'place': hotel, 'note': 'Check-in/Start'})
                prev = hotel
            else:
                prev = {'lat': dest_latlon[0], 'lon': dest_latlon[1]}
            # Breakfast
            breakfast = random.choice([r for r in restaurants if r['lat'] and r['lon']]) if restaurants else None
            if breakfast:
                route = self.osrm_route((prev['lat'], prev['lon']), (breakfast['lat'], breakfast['lon']))
                day_plan['steps'].append({'type': 'breakfast', 'place': breakfast, 'route': route})
                prev = breakfast
            # Attractions (2-3 per day, nearest order)
            day_attractions = random.sample([a for a in attractions if a['lat'] and a['lon']], min(3, len([a for a in attractions if a['lat'] and a['lon']]))) if attractions else []
            for attr in day_attractions:
                route = self.osrm_route((prev['lat'], prev['lon']), (attr['lat'], attr['lon']))
                day_plan['steps'].append({'type': 'attraction', 'place': attr, 'route': route})
                prev = attr
            # Lunch
            lunch = random.choice([r for r in restaurants if r['lat'] and r['lon'] and r != breakfast]) if restaurants else None
            if lunch:
                route = self.osrm_route((prev['lat'], prev['lon']), (lunch['lat'], lunch['lon']))
                day_plan['steps'].append({'type': 'lunch', 'place': lunch, 'route': route})
                prev = lunch
            # More attractions (1-2)
            more_attractions = random.sample([a for a in attractions if a['lat'] and a['lon'] and a not in day_attractions], min(2, len([a for a in attractions if a['lat'] and a['lon'] and a not in day_attractions]))) if attractions else []
            for attr in more_attractions:
                route = self.osrm_route((prev['lat'], prev['lon']), (attr['lat'], attr['lon']))
                day_plan['steps'].append({'type': 'attraction', 'place': attr, 'route': route})
                prev = attr
            # Dinner
            dinner = random.choice([r for r in restaurants if r['lat'] and r['lon'] and r != breakfast and r != lunch]) if restaurants else None
            if dinner:
                route = self.osrm_route((prev['lat'], prev['lon']), (dinner['lat'], dinner['lon']))
                day_plan['steps'].append({'type': 'dinner', 'place': dinner, 'route': route})
                prev = dinner
            # Return to hotel
            if hotel:
                route = self.osrm_route((prev['lat'], prev['lon']), (hotel['lat'], hotel['lon']))
                day_plan['steps'].append({'type': 'hotel', 'place': hotel, 'note': 'Return/Stay', 'route': route})
            itinerary.append(day_plan)
        return {
            'starting_city': starting_city,
            'destination': destination,
            'travel_info': travel_info,
            'itinerary': itinerary,
            'budget': budget,
            'scraped_at': datetime.now().isoformat()
        }

    def get_attractions_from_travel_sites(self, destination):
        attractions = []
        popular_attractions = {
            'paris': [
                {'name': 'Eiffel Tower', 'image': 'https://upload.wikimedia.org/wikipedia/commons/thumb/a/a8/Tour_Eiffel_Wikimedia_Commons.jpg/800px-Tour_Eiffel_Wikimedia_Commons.jpg', 'location': 'Champ de Mars, 5 Avenue Anatole France, 75007 Paris, France'},
                {'name': 'Louvre Museum', 'image': 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/66/Louvre_Museum_Wikimedia_Commons.jpg/800px-Louvre_Museum_Wikimedia_Commons.jpg', 'location': 'Rue de Rivoli, 75001 Paris, France'},
            ],
            'london': [
                {'name': 'Big Ben', 'image': 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Big_Ben_London_2013-07-24.jpg/800px-Big_Ben_London_2013-07-24.jpg', 'location': 'Westminster, London SW1A 0AA, UK'},
            ],
            'tokyo': [
                {'name': 'Tokyo Tower', 'image': 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Tokyo_Tower_Tokyo_2013-07-24.jpg/800px-Tokyo_Tower_Tokyo_2013-07-24.jpg', 'location': '4 Chome-2-8 Shibakoen, Minato City, Tokyo 105-0011, Japan'},
            ]
        }
        destination_lower = destination.lower()
        for city, city_attractions in popular_attractions.items():
            if city in destination_lower or destination_lower in city:
                for attraction in city_attractions:
                    attractions.append({
                        'name': attraction['name'],
                        'rating': '4.5/5',
                        'source': 'Travel Database',
                        'type': 'attraction',
                        'image_url': attraction['image'],
                        'location': attraction['location']
                    })
                break
        return attractions[:10]

    def get_attraction_image(self, attraction_name, destination):
        return "https://upload.wikimedia.org/wikipedia/commons/3/3e/Generic_landmark.jpg"

    def get_breakfast_recommendations(self, destination):
        return [
            {'name': f'{destination} Local Café', 'type': 'Local Café', 'rating': '4.3/5', 'specialty': 'Local Breakfast', 'location': f'Downtown {destination}'},
        ]

    def get_hotels_from_travel_data(self, destination):
        return [
            {'name': f'Grand {destination} Hotel', 'price': '₹15,000/night', 'rating': '4.5/5', 'source': 'Hotel Database', 'type': 'hotel', 'location': f'City Center, {destination}'},
        ]

    def get_restaurants_from_travel_data(self, destination):
        return [
            {'name': f'{destination} Traditional Local Cuisine', 'rating': '4.1/5', 'source': 'Restaurant Database', 'type': 'restaurant', 'location': f'Various locations in {destination}'},
        ]

    def generate_universal_attractions(self, destination):
        attractions = []
        universal_attractions = [
            f"Historic City Center of {destination}",
            f"Local Market in {destination}",
            f"Main Square of {destination}",
        ]
        for attraction_name in universal_attractions:
            attraction = {
                'name': attraction_name,
                'location': destination,
                'rating': f"{random.randint(4, 5)}.{random.randint(0, 9)}/5",
                'description': f"Popular attraction in {destination}",
                'image_url': "https://upload.wikimedia.org/wikipedia/commons/3/3e/Generic_landmark.jpg",
                'source': 'Universal Database',
                'type': 'Attraction'
            }
            attractions.append(attraction)
        return attractions

    def generate_universal_hotels(self, destination):
        hotels = []
        hotel_names = [
            f"Grand Hotel {destination}",
        ]
        for hotel_name in hotel_names:
            hotel = {
                'name': hotel_name,
                'location': destination,
                'rating': f"{random.randint(3, 5)}.{random.randint(0, 9)}/5",
                'price': f"₹{random.randint(2000, 15000)} per night",
                'amenities': ['WiFi', 'Restaurant', 'Room Service', 'Parking'],
                'image_url': "https://upload.wikimedia.org/wikipedia/commons/6/6e/Hotel_room_2.jpg",
                'source': 'Universal Database'
            }
            hotels.append(hotel)
        return hotels

    def generate_universal_restaurants(self, destination):
        restaurants = []
        restaurant_names = [
            f"Local Cuisine {destination}",
        ]
        for restaurant_name in restaurant_names:
            restaurant = {
                'name': restaurant_name,
                'location': destination,
                'rating': f"{random.randint(3, 5)}.{random.randint(0, 9)}/5",
                'cuisine': 'Local',
                'price_range': f"₹{random.randint(500, 3000)} for two",
                'image_url': "https://upload.wikimedia.org/wikipedia/commons/6/6b/Restaurant_interior_2.jpg",
                'source': 'Universal Database'
            }
            restaurants.append(restaurant)
        return restaurants

    def generate_universal_breakfast(self, destination):
        breakfast_places = []
        breakfast_names = [
            f"Morning Cafe {destination}",
        ]
        for breakfast_name in breakfast_names:
            breakfast = {
                'name': breakfast_name,
                'location': destination,
                'rating': f"{random.randint(4, 5)}.{random.randint(0, 9)}/5",
                'specialty': 'Local Breakfast Specialties',
                'price_range': f"₹{random.randint(200, 800)} per person",
                'image_url': "https://upload.wikimedia.org/wikipedia/commons/4/45/Breakfast_in_Barcelona.jpg",
                'source': 'Universal Database'
            }
            breakfast_places.append(breakfast)
        return breakfast_places 
"""Product catalog seeding and mock store catalog data."""

from decimal import Decimal
from typing import List
from sqlalchemy.orm import Session
from app.models import Product

SEED_PRODUCTS = [
    {
        "name": "Sony WH-1000XM5 Wireless Headphones",
        "description": "Industry-leading noise cancelling with two processors and 8 microphones for exceptional sound quality.",
        "price": Decimal("299.99"),
        "category": "Electronics",
        "merchant": "TechHub",
        "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&auto=format&fit=crop&q=60",
        "in_stock": True,
    },
    {
        "name": "Anker 7-in-1 USB-C Hub Adapter",
        "description": "Multi-port adapter featuring 4K HDMI, 100W Power Delivery, SD/TF card reader, and USB-A 3.0 ports.",
        "price": Decimal("34.99"),
        "category": "Electronics",
        "merchant": "TechHub",
        "image_url": "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=500&auto=format&fit=crop&q=60",
        "in_stock": True,
    },
    {
        "name": "Keychron K2 Mechanical Keyboard",
        "description": "75% layout wireless mechanical keyboard with Gateron G Pro Brown switches and RGB backlighting.",
        "price": Decimal("79.99"),
        "category": "Electronics",
        "merchant": "TechHub",
        "image_url": "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=500&auto=format&fit=crop&q=60",
        "in_stock": False,  # Useful for out-of-stock validation testing
    },
    {
        "name": "Designing Data-Intensive Applications",
        "description": "By Martin Kleppmann. The definitive guide to the architecture, data models, and trade-offs of reliable systems.",
        "price": Decimal("44.50"),
        "category": "Books",
        "merchant": "BookWorld",
        "image_url": "https://images.unsplash.com/photo-1544947950-fa07a98d237f?w=500&auto=format&fit=crop&q=60",
        "in_stock": True,
    },
    {
        "name": "Clean Code: A Handbook of Agile Software Craftsmanship",
        "description": "By Robert C. Martin. Practical principles and best practices for writing maintainable software.",
        "price": Decimal("38.99"),
        "category": "Books",
        "merchant": "BookWorld",
        "image_url": "https://images.unsplash.com/photo-1532012164546-f432f2e3777f?w=500&auto=format&fit=crop&q=60",
        "in_stock": True,
    },
    {
        "name": "System Design Interview – An Insider's Guide",
        "description": "By Alex Xu. Step-by-step guidance and diagrams for solving large-scale distributed systems problems.",
        "price": Decimal("39.99"),
        "category": "Books",
        "merchant": "BookWorld",
        "image_url": "https://images.unsplash.com/photo-1512820790803-83ca734da794?w=500&auto=format&fit=crop&q=60",
        "in_stock": True,
    },
    {
        "name": "Fellow Stagg EKG Electric Pour-Over Kettle",
        "description": "Precision temperature control kettle with gooseneck spout for optimal coffee extraction.",
        "price": Decimal("165.00"),
        "category": "Home & Kitchen",
        "merchant": "HomeEssentials",
        "image_url": "https://images.unsplash.com/photo-1517668808822-9ebb02f2a0e6?w=500&auto=format&fit=crop&q=60",
        "in_stock": True,
    },
    {
        "name": "Victorinox 8-Inch Carbon Steel Chef's Knife",
        "description": "Ergonomic Fibrox Pro handle with razor-sharp Swiss high-carbon stainless steel blade.",
        "price": Decimal("48.95"),
        "category": "Home & Kitchen",
        "merchant": "HomeEssentials",
        "image_url": "https://images.unsplash.com/photo-1593618998160-e34014e67546?w=500&auto=format&fit=crop&q=60",
        "in_stock": True,
    },
    {
        "name": "Airtight Glass Food Storage Containers (Set of 4)",
        "description": "Borosilicate glass meal prep containers with leakproof BPA-free locking lids.",
        "price": Decimal("29.99"),
        "category": "Home & Kitchen",
        "merchant": "HomeEssentials",
        "image_url": "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=500&auto=format&fit=crop&q=60",
        "in_stock": True,
    },
    {
        "name": "Classic Merino Wool Crewneck Sweater",
        "description": "Ultra-soft 100% Australian merino wool for lightweight thermal regulation and timeless style.",
        "price": Decimal("89.00"),
        "category": "Clothing",
        "merchant": "FashionForward",
        "image_url": "https://images.unsplash.com/photo-1620799140408-edc6dcb6d633?w=500&auto=format&fit=crop&q=60",
        "in_stock": True,
    },
    {
        "name": "Heavyweight Organic Cotton T-Shirt",
        "description": "Durable 220 GSM combed organic cotton with relaxed fit and reinforced neck ribbing.",
        "price": Decimal("24.50"),
        "category": "Clothing",
        "merchant": "FashionForward",
        "image_url": "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=500&auto=format&fit=crop&q=60",
        "in_stock": True,
    },
    {
        "name": "Weatherproof Commuter Rain Jacket",
        "description": "Breathable 2.5-layer waterproof shell designed with sealed seams and storm flaps.",
        "price": Decimal("129.00"),
        "category": "Clothing",
        "merchant": "FashionForward",
        "image_url": "https://images.unsplash.com/photo-1544923246-77307dd654cb?w=500&auto=format&fit=crop&q=60",
        "in_stock": False,
    },
    {
        "name": "Manduka PRO High-Density Yoga Mat 6mm",
        "description": "Professional non-slip cushioning engineered for joint protection and lifetime durability.",
        "price": Decimal("120.00"),
        "category": "Sports & Outdoors",
        "merchant": "SportZone",
        "image_url": "https://images.unsplash.com/photo-1601925260368-ae2f83cf8b7f?w=500&auto=format&fit=crop&q=60",
        "in_stock": True,
    },
    {
        "name": "Hydro Flask 32oz Wide Mouth Water Bottle",
        "description": "TempShield vacuum insulation keeps beverages ice cold up to 24 hours or piping hot up to 12.",
        "price": Decimal("44.95"),
        "category": "Sports & Outdoors",
        "merchant": "SportZone",
        "image_url": "https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=500&auto=format&fit=crop&q=60",
        "in_stock": True,
    },
    {
        "name": "Adjustable Dumbbell Set (Pair)",
        "description": "Rapid-adjust weight selector from 5 to 52.5 lbs per dumbbell for versatile home workouts.",
        "price": Decimal("279.99"),
        "category": "Sports & Outdoors",
        "merchant": "SportZone",
        "image_url": "https://images.unsplash.com/photo-1584735935682-2f2b69dff9d2?w=500&auto=format&fit=crop&q=60",
        "in_stock": True,
    },
    {
        "name": "Theraband Loop Resistance Bands 3-Pack",
        "description": "Set of 3 progressive resistance latex loops for physical therapy, mobility, and strength training.",
        "price": Decimal("14.99"),
        "category": "Sports & Outdoors",
        "merchant": "SportZone",
        "image_url": "https://images.unsplash.com/photo-1598289431512-b97b0917affc?w=500&auto=format&fit=crop&q=60",
        "in_stock": True,
    },
]


def seed_catalog(db: Session) -> List[Product]:
    """Populate database with initial product catalog if empty.

    Args:
        db: Active SQLAlchemy database session.

    Returns:
        List of all Product objects currently in the database.
    """
    existing_count = db.query(Product).count()
    if existing_count > 0:
        return db.query(Product).all()

    for item in SEED_PRODUCTS:
        product = Product(
            name=item["name"],
            description=item["description"],
            price=item["price"],
            category=item["category"],
            merchant=item["merchant"],
            image_url=item["image_url"],
            in_stock=item["in_stock"],
        )
        db.add(product)

    db.commit()
    return db.query(Product).all()

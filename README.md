# Product management system
## Setting up
### 1 - Cloning this repository
Clone this repository to your local environment:
```Bash
git clone https://github.com/HoangTrungHieuUCLL/DataVisualisation_2025-2026_FOOD_teamF1.git
```
### 2 - Add `.env` file
Create a `.env` file for both front-end and back-end.

#### Front-end
```TypeScript
NEXT_PUBLIC_API_URL=http://localhost:3000
```

#### Back-end
```TypeScript
APP_PORT=3000

DB_USER=<your_local_DB_username>
DB_PASSWORD=<your_local_DB_password>
DB_HOST=localhost
DB_PORT=5432
DB_NAME=food
```

### 3 - Add data to your local pgAdmin4
**Step 1:** In your local port, create a database named `food` and create a table named `product`.

**Step 2:** Right click on the table `product`, choose "Import/Export Data..." and import `view_food_clean.csv` to your database.

## Run the app
### Front-end + Back-end
```Bash
npm install
```
then
```Bash
npm start
```

## Questions for the clients
1. When it comes to products with incomplete information, are we talking about incomplete nutrition values (such as `energy`. `protein`, `ca`, ...)? Or does it extend to columns such as `barcode`, `name`, etc... as well?
2. Is it possible to add more columns to the database?
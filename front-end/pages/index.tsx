import FirstTenProducts from "@components/products/FirstTenProducts";
import { ProductInput } from "@types";
import { useEffect, useState } from "react";
import ProductService from "@services/ProductService";

const Home: React.FC = () => {

    const [products, setProducts] = useState<ProductInput[]>([]);

    useEffect(() => {
        getFirstTenProducts();
    }, []);

    const getFirstTenProducts = async () => {
        try {
            const response = await ProductService.getFirstTenProducts();
            if (!response.ok) {
                console.error("Error fetching first ten products: HTTP", response.status);
                return;
            }
            const data = (await response.json()) as ProductInput[];
            setProducts(data);
        } catch (error) {
            console.error("Error fetching first ten products:", error);
        }
    };

    return (
        <div>
            <FirstTenProducts firstTenProducts={products} />
        </div>
    );
};

export default Home;
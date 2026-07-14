// Sample TypeScript client for twin extraction

export async function fetchItems(): Promise<Item[]> {
  const res = await fetch("/items");
  const data = await res.json();
  return data.items;
}

export const ItemCard = (props: { name: string }) => {
  const [open, setOpen] = useState(false);
  return open ? props.name : "closed";
};

export function useItems() {
  return fetchItems();
}

interface Item {
  id: number;
  name: string;
}

import { useEffect, useState } from "react";
import { memoryStore } from "ra-core";

import { CRM } from "@/components/atomic-crm/root/CRM";
import {
  authProvider,
  createDataProvider,
} from "@/components/atomic-crm/providers/fakerest";
import {
  DEFAULT_USER,
  USER_STORAGE_KEY,
} from "@/components/atomic-crm/providers/fakerest/authProvider";
import type { Db } from "@/components/atomic-crm/providers/fakerest/dataGenerator/types";

const emptyDatabase: Db = {
  companies: [],
  contacts: [],
  contact_notes: [],
  deals: [],
  deal_notes: [],
  sales: [DEFAULT_USER],
  tags: [],
  tasks: [],
  configuration: [{ id: 1, config: {} }],
};

const loadDatabase = async (): Promise<Db> => {
  localStorage.clear();
  sessionStorage.clear();
  localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(DEFAULT_USER));

  const response = await fetch("./seed.json", { cache: "no-store" });
  if (!response.ok) {
    return emptyDatabase;
  }

  const seed = (await response.json()) as Partial<Db>;
  return {
    ...emptyDatabase,
    ...seed,
    sales: seed.sales?.length ? seed.sales : emptyDatabase.sales,
    configuration: seed.configuration?.length
      ? seed.configuration
      : emptyDatabase.configuration,
  };
};

const App = () => {
  const [database, setDatabase] = useState<Db>();
  const [error, setError] = useState<Error>();

  useEffect(() => {
    delete document.documentElement.dataset.waltReady;
    delete document.documentElement.dataset.waltError;
    loadDatabase().then(setDatabase).catch(setError);

    return () => {
      delete document.documentElement.dataset.waltReady;
      delete document.documentElement.dataset.waltError;
    };
  }, []);

  useEffect(() => {
    if (database) {
      document.documentElement.dataset.waltReady = "true";
    }
  }, [database]);

  useEffect(() => {
    if (error) {
      document.documentElement.dataset.waltError = error.message;
    }
  }, [error]);

  if (error) {
    return <p>Atomic could not load the demo data.</p>;
  }

  if (!database) {
    return <p>Preparing Atomic…</p>;
  }

  return (
    <CRM
      dataProvider={createDataProvider({ db: database })}
      authProvider={authProvider}
      store={memoryStore()}
    />
  );
};

export default App;

import { useEffect, useState } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

function App() {
  const [data, setData] = useState(null);

  const [name, setName] = useState("");
  const [wattage, setWattage] = useState("");
  const [priority, setPriority] = useState("");

  const [message, setMessage] = useState("");

  // Load appliances
  const loadAppliances = async () => {
    try {
      const response = await fetch(`${API_URL}/appliances`);
      const result = await response.json();
      setData(result);
    } catch (error) {
      setMessage("Could not connect to backend.");
    }
  };

  // Load when page opens
  useEffect(() => {
    loadAppliances();
  }, []);

  // Create appliance
  const createAppliance = async (event) => {
    event.preventDefault();

    try {
      const response = await fetch(`${API_URL}/appliances`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: name,
          wattage: Number(wattage),
          priority: Number(priority),
        }),
      });

      const result = await response.json();

      if (!response.ok) {
        setMessage(result.detail || "Could not create appliance.");
        return;
      }

      setMessage(`${result.name} added successfully.`);

      setName("");
      setWattage("");
      setPriority("");

      loadAppliances();
    } catch (error) {
      setMessage("Could not connect to backend.");
    }
  };

  // Turn ON
  const turnOn = async (id) => {
    try {
      const response = await fetch(
        `${API_URL}/appliances/${id}/on`,
        {
          method: "POST",
        }
      );

      const result = await response.json();

      if (!response.ok) {
        setMessage(result.detail || "Request rejected.");
      } else {
        setMessage(result.message);

        if (
          result.shed_appliances &&
          result.shed_appliances.length > 0
        ) {
          setMessage(
            `${result.message}. System shed: ${result.shed_appliances.join(", ")}`
          );
        }
      }

      loadAppliances();
    } catch (error) {
      setMessage("Could not connect to backend.");
    }
  };

  // Turn OFF
  const turnOff = async (id) => {
    try {
      const response = await fetch(
        `${API_URL}/appliances/${id}/off`,
        {
          method: "POST",
        }
      );

      const result = await response.json();

      if (!response.ok) {
        setMessage(result.detail || "Could not turn off appliance.");
      } else {
        let text = result.message;

        if (
          result.restored_appliances &&
          result.restored_appliances.length > 0
        ) {
          text += ` Restored: ${result.restored_appliances.join(", ")}`;
        }

        setMessage(text);
      }

      loadAppliances();
    } catch (error) {
      setMessage("Could not connect to backend.");
    }
  };

  // Delete appliance
  const deleteAppliance = async (id, applianceName) => {
    const confirmed = window.confirm(
      `Are you sure you want to delete ${applianceName}?`
    );

    if (!confirmed) {
      return;
    }

    try {
      const response = await fetch(
        `${API_URL}/appliances/${id}`,
        {
          method: "DELETE",
        }
      );

      const result = await response.json();

      if (!response.ok) {
        setMessage(result.detail || "Could not delete appliance.");
      } else {
        let text = result.message;

        if (
          result.restored_appliances &&
          result.restored_appliances.length > 0
        ) {
          text += ` Restored: ${result.restored_appliances.join(", ")}`;
        }

        setMessage(text);
      }

      loadAppliances();
    } catch (error) {
      setMessage("Could not connect to backend.");
    }
  };

  if (!data) {
    return (
      <div className="loading">
        Loading inverter system...
      </div>
    );
  }

  const percentage =
    (data.current_load / data.capacity) * 100;

  return (
    <div className="app">

      <header>
        <h1>⚡ Inverter Load Manager</h1>
        <p>
          Manage appliances and keep total power below 800W.
        </p>
      </header>

      {/* Capacity Section */}
      <section className="capacity-card">

        <div className="capacity-header">
          <h2>Power Capacity</h2>

          <strong>
            {data.current_load}W / {data.capacity}W
          </strong>
        </div>

        <div className="capacity-bar">
          <div
            className="capacity-used"
            style={{
              width: `${percentage}%`,
            }}
          ></div>
        </div>

        <div className="capacity-details">
          <span>
            Used: {data.current_load}W
          </span>

          <span>
            Free: {data.remaining_capacity}W
          </span>
        </div>

      </section>


      {/* Message */}
      {message && (
        <div className="message">
          {message}
        </div>
      )}


      {/* Add Appliance */}
      <section className="form-card">

        <h2>Register Appliance</h2>

        <form onSubmit={createAppliance}>

          <input
            type="text"
            placeholder="Appliance name"
            value={name}
            onChange={(event) =>
              setName(event.target.value)
            }
            required
          />

          <input
            type="number"
            placeholder="Wattage"
            value={wattage}
            onChange={(event) =>
              setWattage(event.target.value)
            }
            min="1"
            required
          />

          <input
            type="number"
            placeholder="Priority (1 = highest)"
            value={priority}
            onChange={(event) =>
              setPriority(event.target.value)
            }
            min="1"
            required
          />

          <button type="submit">
            Add Appliance
          </button>

        </form>

      </section>


      {/* Appliance List */}
      <section className="appliance-section">

        <h2>Appliances</h2>

        {data.appliances.length === 0 ? (

          <p className="empty">
            No appliances registered yet.
          </p>

        ) : (

          <div className="appliance-grid">

            {data.appliances.map((appliance) => (

              <div
                className="appliance-card"
                key={appliance.id}
              >

                <div className="appliance-info">

                  <h3>
                    {appliance.name}
                  </h3>

                  <p>
                    ⚡ {appliance.wattage}W
                  </p>

                  <p>
                    Priority: {appliance.priority}
                  </p>

                </div>


                <div className="appliance-actions">

                  <span
                    className={`state ${appliance.state.toLowerCase()}`}
                  >
                    {appliance.state}
                  </span>


                  <div className="buttons">

                    <button
                      className="on-button"
                      onClick={() =>
                        turnOn(appliance.id)
                      }
                    >
                      ON
                    </button>

                    <button
                      className="off-button"
                      onClick={() =>
                        turnOff(appliance.id)
                      }
                    >
                      OFF
                    </button>

                    <button
                      className="delete-button"
                      onClick={() =>
                        deleteAppliance(
                          appliance.id,
                          appliance.name
                        )
                      }
                    >
                      Delete
                    </button>

                  </div>

                </div>

              </div>

            ))}

          </div>

        )}

      </section>

    </div>
  );
}

export default App;